package com.fieldverify.reader;

import android.app.Application;

import androidx.annotation.Nullable;

import com.credenceid.tap2idSdk.api.models.LicenseKeyVerificationResult;
import com.fieldverify.reader.api.BackendClient;
import com.fieldverify.reader.reader.Tap2iDVerifier;

import java.util.ArrayList;
import java.util.List;

/** App-wide singletons: the backend client and the Tap2iD reader (initialized once per process). */
public class FieldVerifyApp extends Application {

    public enum ReaderState { NOT_CONFIGURED, INITIALIZING, READY, FAILED }

    public interface ReaderStateListener {
        void onReaderStateChanged(ReaderState state, @Nullable String detail);
    }

    private BackendClient backend;
    private Tap2iDVerifier verifier;
    private ReaderState readerState = ReaderState.INITIALIZING;
    private String readerDetail;
    private final List<ReaderStateListener> listeners = new ArrayList<>();

    @Override
    public void onCreate() {
        super.onCreate();
        backend = new BackendClient(BuildConfig.BACKEND_URL, BuildConfig.DEVICE_TOKEN);
        verifier = new Tap2iDVerifier(this);
        initReader();
    }

    public static FieldVerifyApp from(android.content.Context context) {
        return (FieldVerifyApp) context.getApplicationContext();
    }

    public BackendClient backend() {
        return backend;
    }

    public Tap2iDVerifier verifier() {
        return verifier;
    }

    public ReaderState readerState() {
        return readerState;
    }

    @Nullable
    public String readerDetail() {
        return readerDetail;
    }

    /** Missing local.properties values, listed for the start screen. Empty when fully configured. */
    public List<String> missingConfig() {
        List<String> missing = new ArrayList<>();
        if (BuildConfig.TAP2ID_API_KEY.isEmpty()) {
            missing.add("TAP2ID_API_KEY");
        }
        if (BuildConfig.DEVICE_TOKEN.isEmpty()) {
            missing.add("DEVICE_TOKEN");
        }
        return missing;
    }

    /** Validates the Tap2iD license with Credence. Safe to call again after a failure. */
    public void initReader() {
        if (BuildConfig.TAP2ID_API_KEY.isEmpty()) {
            setReaderState(ReaderState.NOT_CONFIGURED, "TAP2ID_API_KEY is not set in local.properties.");
            return;
        }
        setReaderState(ReaderState.INITIALIZING, null);
        verifier.init(BuildConfig.TAP2ID_API_KEY, new Tap2iDVerifier.InitCallback() {
            @Override
            public void onReady(LicenseKeyVerificationResult license) {
                String profile = license.getProfileName() == null ? "no profile name" : license.getProfileName();
                setReaderState(ReaderState.READY, "SDK " + verifier.getSdkVersion() + " · " + profile);
            }

            @Override
            public void onFailed(String message) {
                setReaderState(ReaderState.FAILED, message);
            }
        });
    }

    public void addReaderStateListener(ReaderStateListener l) {
        listeners.add(l);
        l.onReaderStateChanged(readerState, readerDetail);
    }

    public void removeReaderStateListener(ReaderStateListener l) {
        listeners.remove(l);
    }

    private void setReaderState(ReaderState state, @Nullable String detail) {
        readerState = state;
        readerDetail = detail;
        for (ReaderStateListener l : new ArrayList<>(listeners)) {
            l.onReaderStateChanged(state, detail);
        }
    }
}
