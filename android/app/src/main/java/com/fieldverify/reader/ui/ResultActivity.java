package com.fieldverify.reader.ui;

import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.Bundle;
import android.util.Base64;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.annotation.Nullable;
import androidx.core.content.ContextCompat;

import com.fieldverify.reader.FieldVerifyApp;
import com.fieldverify.reader.R;
import com.fieldverify.reader.api.BackendClient;
import com.fieldverify.reader.api.Models;

import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.Map;

/**
 * Shows the backend's verdict: authenticity (from Credence's checks) and the record match, kept as two separate
 * signals. Lets the auditor complete an age-check result with the physical ID's details, then save to the audit log.
 */
public class ResultActivity extends BaseActivity {

    static final String EXTRA_RESULT_JSON = "result_json";

    private FieldVerifyApp app;
    private Models.VerificationResult result;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setUpScreen(R.layout.activity_result, true);
        app = FieldVerifyApp.from(this);
        String json = savedInstanceState != null ? savedInstanceState.getString(EXTRA_RESULT_JSON)
                : getIntent().getStringExtra(EXTRA_RESULT_JSON);
        result = BackendClient.GSON.fromJson(json, Models.VerificationResult.class);

        findViewById(R.id.button_supplement).setOnClickListener(v -> submitSupplement());
        findViewById(R.id.button_save).setOnClickListener(v -> save());
        findViewById(R.id.button_done).setOnClickListener(v -> backToVisits());
        render();
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        outState.putString(EXTRA_RESULT_JSON, BackendClient.GSON.toJson(result));
    }

    @Override
    public boolean onSupportNavigateUp() {
        backToVisits();
        return true;
    }

    private void backToVisits() {
        Intent intent = new Intent(this, MainActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        startActivity(intent);
        finish();
    }

    private void render() {
        TextView banner = findViewById(R.id.outcome_banner);
        banner.setText(result.outcome.label);
        banner.setBackgroundResource(bannerBackground(result.outcome.color));
        banner.setTextColor(ContextCompat.getColor(this, textColor(result.outcome.color)));

        ((TextView) findViewById(R.id.result_provider)).setText(
                getString(R.string.result_provider, result.provider.name, result.provider.npi));

        // Authenticity
        boolean genuine = "verified".equals(result.authenticity.status);
        TextView authStatus = findViewById(R.id.auth_status);
        authStatus.setText(genuine ? R.string.auth_verified : R.string.auth_failed);
        authStatus.setTextColor(ContextCompat.getColor(this, genuine ? R.color.green_text : R.color.red_text));
        TextView issuer = findViewById(R.id.auth_issuer);
        issuer.setText(result.authenticity.issuer == null ? getString(R.string.issuer_unknown)
                : getString(R.string.issuer_label, result.authenticity.issuer));
        LinearLayout checks = findViewById(R.id.auth_checks);
        checks.removeAllViews();
        for (Map.Entry<String, Boolean> e : result.authenticity.checks.entrySet()) {
            addRow(checks, Format.checkName(e.getKey()), Boolean.TRUE.equals(e.getValue()) ? "✓" : "✗", null);
        }
        for (Map.Entry<String, Boolean> e : result.attributes.entrySet()) {
            addRow(checks, Format.title(e.getKey()), Boolean.TRUE.equals(e.getValue()) ? "Yes" : "No", null);
        }

        ImageView portrait = findViewById(R.id.portrait);
        Bitmap bitmap = decodePortrait(result.portraitDataUrl);
        portrait.setVisibility(bitmap == null ? View.GONE : View.VISIBLE);
        findViewById(R.id.portrait_hint).setVisibility(bitmap == null ? View.GONE : View.VISIBLE);
        if (bitmap != null) {
            portrait.setImageBitmap(bitmap);
        }

        // Record match
        TextView matchSummary = findViewById(R.id.match_summary);
        matchSummary.setText(getString(R.string.match_summary, result.match.score, Format.title(result.match.band),
                sourceLabel(result.matchSource)));
        LinearLayout fields = findViewById(R.id.match_fields);
        fields.removeAllViews();
        for (Models.FieldResult f : result.match.fields) {
            addRow(fields, Format.fieldName(f.field), Format.title(f.result) + " · " + Format.points(f.points, f.max),
                    f.reason);
        }
        for (String cap : result.match.caps) {
            addRow(fields, getString(R.string.cap_label), "", cap);
        }

        // Age-check completion and save
        findViewById(R.id.supplement_section).setVisibility(result.needsIdDetails() ? View.VISIBLE : View.GONE);
        boolean photoAlreadyConfirmed = Boolean.TRUE.equals(result.photoChecked);
        findViewById(R.id.save_photo_check).setVisibility(
                photoAlreadyConfirmed || result.portraitDataUrl == null ? View.GONE : View.VISIBLE);
        Button save = findViewById(R.id.button_save);
        save.setEnabled(!result.saved);
        save.setText(result.saved ? R.string.saved : R.string.save_to_audit);
    }

    private void addRow(LinearLayout parent, String label, String value, @Nullable String detail) {
        View row = LayoutInflater.from(this).inflate(R.layout.item_row, parent, false);
        ((TextView) row.findViewById(R.id.row_label)).setText(label);
        ((TextView) row.findViewById(R.id.row_value)).setText(value);
        TextView detailView = row.findViewById(R.id.row_detail);
        if (detail == null || detail.isEmpty()) {
            detailView.setVisibility(View.GONE);
        } else {
            detailView.setText(detail);
        }
        parent.addView(row);
    }

    private void submitSupplement() {
        CheckBox photo = findViewById(R.id.supplement_photo_check);
        EditText first = findViewById(R.id.supplement_first);
        EditText last = findViewById(R.id.supplement_last);
        EditText dob = findViewById(R.id.supplement_dob);
        TextView error = findViewById(R.id.supplement_error);
        String lastName = last.getText().toString().trim();
        String dobText = dob.getText().toString().trim();
        String problem = null;
        if (!photo.isChecked()) {
            problem = getString(R.string.photo_required);
        } else if (lastName.isEmpty()) {
            problem = getString(R.string.last_name_required);
        } else if (!isIsoDate(dobText)) {
            problem = getString(R.string.dob_format);
        }
        if (problem != null) {
            error.setText(problem);
            error.setVisibility(View.VISIBLE);
            return;
        }
        error.setVisibility(View.GONE);
        Button button = findViewById(R.id.button_supplement);
        button.setEnabled(false);
        app.backend().supplement(result.id, true, first.getText().toString().trim(), lastName, dobText,
                new BackendClient.Callback<Models.VerificationResult>() {
                    @Override
                    public void onSuccess(Models.VerificationResult value) {
                        button.setEnabled(true);
                        result = value;
                        render();
                    }

                    @Override
                    public void onError(String message) {
                        button.setEnabled(true);
                        error.setText(message);
                        error.setVisibility(View.VISIBLE);
                    }
                });
    }

    private void save() {
        CheckBox photo = findViewById(R.id.save_photo_check);
        EditText notes = findViewById(R.id.notes);
        TextView status = findViewById(R.id.save_status);
        Boolean photoChecked = photo.getVisibility() == View.VISIBLE ? photo.isChecked() : null;
        Button save = findViewById(R.id.button_save);
        save.setEnabled(false);
        app.backend().saveToAudit(result.id, photoChecked, notes.getText().toString(),
                new BackendClient.Callback<Models.AuditEntry>() {
                    @Override
                    public void onSuccess(Models.AuditEntry entry) {
                        result.saved = true;
                        render();
                        status.setText(getString(R.string.saved_entry, entry.id));
                        status.setVisibility(View.VISIBLE);
                    }

                    @Override
                    public void onError(String message) {
                        save.setEnabled(true);
                        status.setText(message);
                        status.setVisibility(View.VISIBLE);
                    }
                });
    }

    private String sourceLabel(String source) {
        if ("wallet".equals(source)) {
            return getString(R.string.source_wallet);
        }
        if ("id_details".equals(source)) {
            return getString(R.string.source_id_details);
        }
        return getString(R.string.source_none);
    }

    static boolean isIsoDate(String text) {
        try {
            LocalDate.parse(text);
            return true;
        } catch (DateTimeParseException e) {
            return false;
        }
    }

    @Nullable
    private static Bitmap decodePortrait(@Nullable String dataUrl) {
        if (dataUrl == null) {
            return null;
        }
        int comma = dataUrl.indexOf(',');
        if (!dataUrl.startsWith("data:image/") || comma < 0) {
            return null;
        }
        try {
            byte[] bytes = Base64.decode(dataUrl.substring(comma + 1), Base64.DEFAULT);
            return BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
        } catch (IllegalArgumentException e) {
            return null;
        }
    }

    private static int bannerBackground(String color) {
        if ("green".equals(color)) {
            return R.drawable.bg_status_green;
        }
        if ("yellow".equals(color)) {
            return R.drawable.bg_status_yellow;
        }
        return R.drawable.bg_status_red;
    }

    private static int textColor(String color) {
        if ("green".equals(color)) {
            return R.color.green_text;
        }
        if ("yellow".equals(color)) {
            return R.color.yellow_text;
        }
        return R.color.red_text;
    }
}
