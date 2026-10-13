package com.fieldverify.reader.ui;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.nfc.NfcAdapter;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.util.Log;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.annotation.Nullable;
import androidx.core.content.ContextCompat;

import com.credenceid.tap2idSdk.api.models.VerificationStage;
import com.credenceid.tap2idSdk.core.model.VerificationResult;
import com.fieldverify.reader.FieldVerifyApp;
import com.fieldverify.reader.R;
import com.fieldverify.reader.api.BackendClient;
import com.fieldverify.reader.api.Models;
import com.fieldverify.reader.reader.Tap2iDPayload;
import com.fieldverify.reader.reader.Tap2iDVerifier;
import com.google.android.material.progressindicator.LinearProgressIndicator;
import com.journeyapps.barcodescanner.ScanContract;
import com.journeyapps.barcodescanner.ScanOptions;

import java.util.ArrayList;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;

/**
 * Reads the provider's mobile ID in person with Tap2iD (NFC tap or wallet QR), then sends the raw result to the
 * backend, which checks authenticity and scores it against the enrollment record.
 */
public class VerifyActivity extends BaseActivity implements Tap2iDVerifier.ReadCallback {

    static final String EXTRA_VISIT_JSON = "visit_json";
    private static final String TAG = "FieldVerify";

    private enum Engagement { NFC, QR }

    private FieldVerifyApp app;
    private Models.Visit visit;
    private Button nfcButton;
    private Button qrButton;
    private Button cancelButton;
    private TextView stageLog;
    private TextView errorText;
    private LinearProgressIndicator progress;
    private final Map<VerificationStage, String> stages = new EnumMap<>(VerificationStage.class);
    private boolean reading;
    private Engagement pending;

    private final ActivityResultLauncher<String[]> permissionLauncher = registerForActivityResult(
            new ActivityResultContracts.RequestMultiplePermissions(), granted -> {
                if (granted.containsValue(false)) {
                    showError(getString(R.string.permissions_needed));
                    pending = null;
                } else if (pending != null) {
                    Engagement next = pending;
                    pending = null;
                    start(next);
                }
            });

    private final ActivityResultLauncher<ScanOptions> qrLauncher = registerForActivityResult(
            new ScanContract(), result -> {
                String text = result.getContents();
                if (text == null) {
                    return; // scanner cancelled
                }
                if (!text.startsWith("mdoc:")) {
                    showError(getString(R.string.not_mdoc_qr));
                    return;
                }
                beginReading();
                app.verifier().readWithQr(text, this);
            });

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setUpScreen(R.layout.activity_verify, true);
        app = FieldVerifyApp.from(this);
        visit = BackendClient.GSON.fromJson(getIntent().getStringExtra(EXTRA_VISIT_JSON), Models.Visit.class);

        ((TextView) findViewById(R.id.provider_name)).setText(visit.provider.name);
        ((TextView) findViewById(R.id.provider_details)).setText(
                getString(R.string.visit_details, visit.provider.npi, visit.provider.specialty));
        ((TextView) findViewById(R.id.visit_address)).setText(visit.siteAddress);

        nfcButton = findViewById(R.id.button_nfc);
        qrButton = findViewById(R.id.button_qr);
        cancelButton = findViewById(R.id.button_cancel);
        stageLog = findViewById(R.id.stage_log);
        errorText = findViewById(R.id.error_text);
        progress = findViewById(R.id.progress);

        nfcButton.setOnClickListener(v -> requestThenStart(Engagement.NFC));
        qrButton.setOnClickListener(v -> requestThenStart(Engagement.QR));
        cancelButton.setOnClickListener(v -> {
            app.verifier().cancel();
            endReading();
        });
    }

    @Override
    public boolean onSupportNavigateUp() {
        finish();
        return true;
    }

    @Override
    protected void onDestroy() {
        if (reading) {
            app.verifier().cancel();
        }
        super.onDestroy();
    }

    private void requestThenStart(Engagement engagement) {
        errorText.setVisibility(View.GONE);
        if (app.readerState() != FieldVerifyApp.ReaderState.READY) {
            showError(getString(R.string.reader_not_ready, String.valueOf(app.readerDetail())));
            if (app.readerState() == FieldVerifyApp.ReaderState.FAILED) {
                app.initReader();
            }
            return;
        }
        String[] missing = missingPermissions(engagement);
        if (missing.length > 0) {
            pending = engagement;
            permissionLauncher.launch(missing);
            return;
        }
        start(engagement);
    }

    /** BLE carries the data after engagement. Android 12+ asks for "Nearby devices"; 10-11 need location. */
    private String[] missingPermissions(Engagement engagement) {
        List<String> needed = new ArrayList<>();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            needed.add(Manifest.permission.BLUETOOTH_SCAN);
            needed.add(Manifest.permission.BLUETOOTH_CONNECT);
            needed.add(Manifest.permission.BLUETOOTH_ADVERTISE);
        } else {
            needed.add(Manifest.permission.ACCESS_FINE_LOCATION);
        }
        if (engagement == Engagement.QR) {
            needed.add(Manifest.permission.CAMERA);
        }
        List<String> missing = new ArrayList<>();
        for (String p : needed) {
            if (ContextCompat.checkSelfPermission(this, p) != PackageManager.PERMISSION_GRANTED) {
                missing.add(p);
            }
        }
        return missing.toArray(new String[0]);
    }

    private void start(Engagement engagement) {
        if (engagement == Engagement.NFC) {
            NfcAdapter nfc = NfcAdapter.getDefaultAdapter(this);
            if (nfc == null) {
                showError(getString(R.string.no_nfc));
                return;
            }
            if (!nfc.isEnabled()) {
                showError(getString(R.string.nfc_off));
                startActivity(new Intent(Settings.ACTION_NFC_SETTINGS));
                return;
            }
            beginReading();
            stageLog.setText(R.string.hold_phones_together);
            app.verifier().readWithNfc(this, this);
        } else {
            ScanOptions options = new ScanOptions()
                    .setDesiredBarcodeFormats(ScanOptions.QR_CODE)
                    .setPrompt(getString(R.string.scan_prompt))
                    .setBeepEnabled(false)
                    .setOrientationLocked(false);
            qrLauncher.launch(options);
        }
    }

    private void beginReading() {
        reading = true;
        stages.clear();
        errorText.setVisibility(View.GONE);
        progress.setVisibility(View.VISIBLE);
        nfcButton.setEnabled(false);
        qrButton.setEnabled(false);
        cancelButton.setVisibility(View.VISIBLE);
    }

    private void endReading() {
        reading = false;
        progress.setVisibility(View.GONE);
        nfcButton.setEnabled(true);
        qrButton.setEnabled(true);
        cancelButton.setVisibility(View.GONE);
    }

    private void showError(String message) {
        errorText.setText(message);
        errorText.setVisibility(View.VISIBLE);
    }

    private void renderStages() {
        StringBuilder sb = new StringBuilder();
        for (Map.Entry<VerificationStage, String> e : stages.entrySet()) {
            sb.append(e.getValue()).append("  ").append(stageLabel(e.getKey())).append('\n');
        }
        stageLog.setText(sb.toString().trim());
    }

    private String stageLabel(VerificationStage stage) {
        switch (stage) {
            case NFC_ENGAGEMENT:
                return getString(R.string.stage_nfc);
            case QR_ENGAGEMENT:
                return getString(R.string.stage_qr);
            case CONNECTION:
                return getString(R.string.stage_connection);
            case SEND_MDOC_REQUEST:
                return getString(R.string.stage_request);
            case PARSE_MDOC_RESPONSE:
            default:
                return getString(R.string.stage_response);
        }
    }

    // --- Tap2iDVerifier.ReadCallback (main thread) ---

    @Override
    public void onStageStarted(VerificationStage stage) {
        stages.put(stage, "…");
        renderStages();
    }

    @Override
    public void onStageCompleted(VerificationStage stage) {
        stages.put(stage, "✓");
        renderStages();
    }

    @Override
    public void onStageError(VerificationStage stage, String message) {
        Log.w(TAG, "Tap2iD stage error at " + stage + ": " + message);
        stages.put(stage, "✗");
        renderStages();
        app.verifier().cancel();
        endReading();
        showError(friendlyError(stage, message));
    }

    /** Plain-English versions of the SDK errors seen in testing (docs/android/CONTEXT.md §7); raw text otherwise. */
    private String friendlyError(VerificationStage stage, String message) {
        String m = message == null ? "" : message;
        if (m.contains("Transceive failed")) {
            return getString(R.string.err_nfc_dropped);
        }
        if (m.contains("CODE :216") || m.toLowerCase(java.util.Locale.US).contains("provide consent")) {
            return getString(R.string.err_no_consent);
        }
        if (m.contains("6A82")) {
            return getString(R.string.err_no_mobile_id);
        }
        return getString(R.string.read_failed, stageLabel(stage), m);
    }

    @Override
    public void onCompleted(VerificationResult result) {
        // Shape only (keys and value classes), never values. Record what a real wallet returns in CONTEXT.md §7.
        Log.i(TAG, "Tap2iD result shape: " + Tap2iDPayload.describeShape(result));
        stageLog.setText(R.string.checking_with_server);
        app.backend().submitTap2id(
                Tap2iDPayload.build(visit.id, app.verifier().getSdkVersion(), result),
                new BackendClient.Callback<Models.VerificationResult>() {
                    @Override
                    public void onSuccess(Models.VerificationResult value) {
                        endReading();
                        Intent intent = new Intent(VerifyActivity.this, ResultActivity.class);
                        intent.putExtra(ResultActivity.EXTRA_RESULT_JSON, BackendClient.GSON.toJson(value));
                        startActivity(intent);
                        finish();
                    }

                    @Override
                    public void onError(String message) {
                        endReading();
                        showError(message);
                    }
                });
    }
}
