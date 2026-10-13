package com.fieldverify.reader.reader;

import com.credenceid.tap2idSdk.core.model.AuthenticationResult;
import com.credenceid.tap2idSdk.core.model.VerificationResult;
import com.credenceid.tap2idSdk.core.model.VerifiedDocument;
import com.credenceid.tap2idSdk.core.model.VerifiedNamespace;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import com.google.gson.JsonPrimitive;

import android.graphics.Bitmap;

import java.io.ByteArrayOutputStream;
import java.time.temporal.TemporalAccessor;
import java.util.Base64;
import java.util.Date;
import java.util.Map;

/**
 * Flattens a Tap2iD {@link VerificationResult} into the JSON body of POST /api/verify/digital/tap2id
 * (docs/android/CONTEXT.md §8). Sends raw check results only; the backend decides authenticity.
 */
public final class Tap2iDPayload {

    private Tap2iDPayload() {
    }

    public static JsonObject build(long visitId, String sdkVersion, VerificationResult result) {
        JsonObject body = new JsonObject();
        body.addProperty("visit_id", visitId);
        body.addProperty("sdk_version", sdkVersion);
        body.addProperty("status", result.getStatus().name());
        JsonArray documents = new JsonArray();
        for (VerifiedDocument doc : result.getDocuments()) {
            documents.add(document(doc));
        }
        body.add("documents", documents);
        return body;
    }

    static JsonObject document(VerifiedDocument doc) {
        AuthenticationResult auth = doc.getAuthentication();
        JsonObject out = new JsonObject();
        out.addProperty("doc_type", doc.getDocType());
        out.addProperty("issuer_signed_valid", auth.getSecurityChecks().isIssuerSignedValid());
        out.addProperty("device_signed_valid", auth.getSecurityChecks().isDeviceSignedValid());
        out.addProperty("digests_valid", auth.getSecurityChecks().getAreDigestsValid());
        out.addProperty("issuer_trusted", auth.getTrustAttributes().isIssuerTrusted());
        out.addProperty("chain_status", auth.getTrustAttributes().getChainStatus().name());
        out.addProperty("mso_status", auth.getMsoValidity().getStatus().name());
        out.addProperty("issuer_dn", auth.getTrustAttributes().getIssuerDistinguishedName());
        JsonArray errors = new JsonArray();
        for (String e : auth.getValidationErrors()) {
            errors.add(e);
        }
        out.add("validation_errors", errors);
        JsonObject namespaces = new JsonObject();
        for (VerifiedNamespace ns : doc.getNameSpaces()) {
            JsonObject attrs = new JsonObject();
            for (Map.Entry<String, Object> entry : ns.getAttributes().entrySet()) {
                attrs.add(entry.getKey(), value(entry.getValue()));
            }
            namespaces.add(ns.getName(), attrs);
        }
        out.add("namespaces", namespaces);
        return out;
    }

    /**
     * The SDK types its attribute map as Map&lt;String, Any?&gt;; the concrete value classes are not documented
     * (CONTEXT.md §11 #2), so convert generically.
     */
    static JsonElement value(Object v) {
        if (v == null) {
            return JsonNull.INSTANCE;
        }
        if (v instanceof String) {
            return new JsonPrimitive((String) v);
        }
        if (v instanceof Boolean) {
            return new JsonPrimitive((Boolean) v);
        }
        if (v instanceof Number) {
            return new JsonPrimitive((Number) v);
        }
        if (v instanceof Bitmap) {
            // Observed Oct 13: the SDK delivers `portrait` as an android.graphics.Bitmap, not JPEG bytes.
            return new JsonPrimitive(Base64.getEncoder().encodeToString(jpeg((Bitmap) v)));
        }
        if (v instanceof Enum) {
            // Observed Oct 13: `age_over_NN` arrives as com.credenceid.identity.iso18013.AgeOverPossibleValues
            // {TRUE, FALSE, NOT_RETRIEVED}. Matched by name so we don't compile against the SDK's internal library.
            String name = ((Enum<?>) v).name();
            if ("TRUE".equals(name)) {
                return new JsonPrimitive(true);
            }
            if ("FALSE".equals(name)) {
                return new JsonPrimitive(false);
            }
            if ("NOT_RETRIEVED".equals(name)) {
                return JsonNull.INSTANCE;
            }
            return new JsonPrimitive(name);
        }
        if (v instanceof byte[]) {
            return new JsonPrimitive(Base64.getEncoder().encodeToString((byte[]) v));
        }
        if (v instanceof TemporalAccessor) {
            return new JsonPrimitive(v.toString()); // LocalDate -> 1971-04-12
        }
        if (v instanceof Date) {
            return new JsonPrimitive(((Date) v).toInstant().toString());
        }
        if (v instanceof Map) {
            JsonObject obj = new JsonObject();
            for (Map.Entry<?, ?> e : ((Map<?, ?>) v).entrySet()) {
                obj.add(String.valueOf(e.getKey()), value(e.getValue()));
            }
            return obj;
        }
        if (v instanceof Iterable) {
            JsonArray arr = new JsonArray();
            for (Object item : (Iterable<?>) v) {
                arr.add(value(item));
            }
            return arr;
        }
        return new JsonPrimitive(v.toString());
    }

    private static byte[] jpeg(Bitmap bitmap) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        bitmap.compress(Bitmap.CompressFormat.JPEG, 90, out);
        return out.toByteArray();
    }

    /** For logcat: document types, namespaces, attribute keys and value classes. Never attribute values. */
    public static String describeShape(VerificationResult result) {
        StringBuilder sb = new StringBuilder("status=").append(result.getStatus());
        for (VerifiedDocument doc : result.getDocuments()) {
            sb.append(" | doc=").append(doc.getDocType())
                    .append(" auth=").append(doc.getAuthentication().getAuthenticationStatus());
            for (VerifiedNamespace ns : doc.getNameSpaces()) {
                sb.append(" ns=").append(ns.getName()).append(" {");
                for (Map.Entry<String, Object> e : ns.getAttributes().entrySet()) {
                    Object val = e.getValue();
                    sb.append(e.getKey()).append(':')
                            .append(val == null ? "null" : val.getClass().getSimpleName()).append(' ');
                }
                sb.append('}');
            }
        }
        return sb.toString();
    }
}
