package com.fieldverify.reader.api;

import android.os.Handler;
import android.os.Looper;

import com.google.gson.FieldNamingPolicy;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.reflect.TypeToken;

import java.io.IOException;
import java.lang.reflect.Type;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;
import okhttp3.ResponseBody;

/**
 * Talks to the FieldVerify backend (the same API the web app uses). Calls run on a background thread and
 * report back on the main thread. Never logs request or response bodies (they can hold identity data).
 */
public class BackendClient {

    public interface Callback<T> {
        void onSuccess(T value);

        void onError(String message);
    }

    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");

    public static final Gson GSON = new GsonBuilder()
            .setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES)
            .create();

    private final String baseUrl;
    private final String deviceToken;
    // Render's free plan sleeps when idle; the first request can take ~a minute to wake it.
    private final OkHttpClient http = new OkHttpClient.Builder()
            .connectTimeout(20, TimeUnit.SECONDS)
            .readTimeout(90, TimeUnit.SECONDS)
            .callTimeout(120, TimeUnit.SECONDS)
            .build();
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());

    public BackendClient(String baseUrl, String deviceToken) {
        this.baseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
        this.deviceToken = deviceToken;
    }

    public String getBaseUrl() {
        return baseUrl;
    }

    public void listVisits(Callback<List<Models.Visit>> cb) {
        Type type = new TypeToken<List<Models.Visit>>() {
        }.getType();
        run(new Request.Builder().url(baseUrl + "/api/visits").get().build(), type, cb);
    }

    /** Sends the flattened Tap2iD result; the backend recomputes authenticity and scores it. */
    public void submitTap2id(JsonObject payload, Callback<Models.VerificationResult> cb) {
        Request request = new Request.Builder()
                .url(baseUrl + "/api/verify/digital/tap2id")
                .header("X-Device-Token", deviceToken)
                .post(RequestBody.create(payload.toString(), JSON))
                .build();
        run(request, Models.VerificationResult.class, cb);
    }

    /** Age-check completion: photo confirmed, name/DOB read off the physical ID (backend ADR-0007). */
    public void supplement(String resultId, boolean photoChecked, String firstName, String lastName, String dobIso,
                           Callback<Models.VerificationResult> cb) {
        JsonObject body = new JsonObject();
        body.addProperty("result_id", resultId);
        body.addProperty("photo_checked", photoChecked);
        if (firstName != null && !firstName.isEmpty()) {
            body.addProperty("first_name", firstName);
        }
        body.addProperty("last_name", lastName);
        body.addProperty("dob", dobIso);
        post("/api/verify/digital/supplement", body, Models.VerificationResult.class, cb);
    }

    public void saveToAudit(String resultId, Boolean photoChecked, String notes, Callback<Models.AuditEntry> cb) {
        JsonObject body = new JsonObject();
        body.addProperty("result_id", resultId);
        body.addProperty("notes", notes == null ? "" : notes);
        if (photoChecked != null) {
            body.addProperty("photo_checked", photoChecked);
        }
        post("/api/audit", body, Models.AuditEntry.class, cb);
    }

    private <T> void post(String path, JsonObject body, Type type, Callback<T> cb) {
        run(new Request.Builder().url(baseUrl + path).post(RequestBody.create(body.toString(), JSON)).build(),
                type, cb);
    }

    private <T> void run(Request request, Type type, Callback<T> cb) {
        executor.execute(() -> {
            try (Response response = http.newCall(request).execute()) {
                ResponseBody body = response.body();
                String text = body == null ? "" : body.string();
                if (!response.isSuccessful()) {
                    String message = errorMessage(response.code(), text);
                    main.post(() -> cb.onError(message));
                    return;
                }
                T value = GSON.fromJson(text, type);
                main.post(() -> cb.onSuccess(value));
            } catch (IOException e) {
                main.post(() -> cb.onError("Can't reach the FieldVerify server (" + e.getClass().getSimpleName()
                        + "). Check the connection and BACKEND_URL."));
            } catch (RuntimeException e) {
                main.post(() -> cb.onError("Unexpected server response."));
            }
        });
    }

    /** Backend errors look like {"error": {"code": "...", "message": "..."}} (backend/app/main.py). */
    static String errorMessage(int status, String text) {
        try {
            JsonElement root = JsonParser.parseString(text);
            if (root.isJsonObject() && root.getAsJsonObject().has("error")) {
                JsonObject err = root.getAsJsonObject().getAsJsonObject("error");
                if (err.has("message")) {
                    return err.get("message").getAsString();
                }
            }
        } catch (RuntimeException ignored) {
            // fall through to the generic message
        }
        if (status == 401) {
            return "This phone isn't registered with the server (device token mismatch).";
        }
        return "Server error (HTTP " + status + ").";
    }
}
