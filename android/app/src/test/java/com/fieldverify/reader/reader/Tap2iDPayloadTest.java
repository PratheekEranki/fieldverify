package com.fieldverify.reader.reader;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import com.credenceid.tap2idSdk.core.model.AuthenticationResult;
import com.credenceid.tap2idSdk.core.model.MsoStatus;
import com.credenceid.tap2idSdk.core.model.MsoValidity;
import com.credenceid.tap2idSdk.core.model.SecurityChecks;
import com.credenceid.tap2idSdk.core.model.TrustAttributes;
import com.credenceid.tap2idSdk.core.model.TrustStatus;
import com.credenceid.tap2idSdk.core.model.VerificationResult;
import com.credenceid.tap2idSdk.core.model.VerificationStatus;
import com.credenceid.tap2idSdk.core.model.VerifiedDocument;
import com.credenceid.tap2idSdk.core.model.VerifiedNamespace;
import com.google.gson.JsonObject;

import org.junit.Test;

import java.time.LocalDate;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Builds results with the SDK's own model classes (public constructors in 2.0.0) and checks the JSON contract. */
public class Tap2iDPayloadTest {

    private static VerificationResult sample(boolean trusted, List<String> errors) {
        Map<String, Object> attrs = new LinkedHashMap<>();
        attrs.put("family_name", "Kowalski");
        attrs.put("birth_date", LocalDate.of(1971, 4, 12));
        attrs.put("portrait", new byte[]{(byte) 0xFF, (byte) 0xD8, (byte) 0xFF});
        attrs.put("age_over_21", true);
        attrs.put("missing", null);
        VerifiedNamespace ns = new VerifiedNamespace("org.iso.18013.5.1", attrs);
        AuthenticationResult auth = new AuthenticationResult(
                new SecurityChecks(true, true, true),
                new MsoValidity(MsoStatus.VALID, 1L, 2L, 3L),
                new TrustAttributes(trusted, trusted ? TrustStatus.VERIFIED : TrustStatus.UNTRUSTED, "CN=IL IACA"),
                errors);
        VerifiedDocument doc = new VerifiedDocument("org.iso.18013.5.1.mDL", Collections.singletonList(ns), auth);
        return new VerificationResult(Collections.singletonList(doc), VerificationStatus.SUCCESS);
    }

    @Test
    public void buildsBackendContract() {
        JsonObject body = Tap2iDPayload.build(7, "2.0.0", sample(true, Collections.emptyList()));
        assertEquals(7, body.get("visit_id").getAsInt());
        assertEquals("SUCCESS", body.get("status").getAsString());
        JsonObject doc = body.getAsJsonArray("documents").get(0).getAsJsonObject();
        assertEquals("org.iso.18013.5.1.mDL", doc.get("doc_type").getAsString());
        assertTrue(doc.get("issuer_signed_valid").getAsBoolean());
        assertTrue(doc.get("digests_valid").getAsBoolean());
        assertEquals("VERIFIED", doc.get("chain_status").getAsString());
        assertEquals("VALID", doc.get("mso_status").getAsString());
        assertEquals("CN=IL IACA", doc.get("issuer_dn").getAsString());
        assertEquals(0, doc.getAsJsonArray("validation_errors").size());

        JsonObject attrs = doc.getAsJsonObject("namespaces").getAsJsonObject("org.iso.18013.5.1");
        assertEquals("Kowalski", attrs.get("family_name").getAsString());
        assertEquals("1971-04-12", attrs.get("birth_date").getAsString());
        assertEquals("/9j/", attrs.get("portrait").getAsString()); // base64 of FF D8 FF (JPEG start)
        assertTrue(attrs.get("age_over_21").getAsBoolean());
        assertTrue(attrs.get("missing").isJsonNull());
    }

    @Test
    public void passesFailuresThroughUnchanged() {
        JsonObject doc = Tap2iDPayload.build(1, "2.0.0", sample(false, Collections.singletonList("bad digest")))
                .getAsJsonArray("documents").get(0).getAsJsonObject();
        assertFalse(doc.get("issuer_trusted").getAsBoolean());
        assertEquals("UNTRUSTED", doc.get("chain_status").getAsString());
        assertEquals("bad digest", doc.getAsJsonArray("validation_errors").get(0).getAsString());
    }

    @Test
    public void shapeLogNeverContainsValues() {
        String shape = Tap2iDPayload.describeShape(sample(true, Collections.emptyList()));
        assertTrue(shape.contains("family_name:String"));
        assertTrue(shape.contains("birth_date:LocalDate"));
        assertFalse(shape.contains("Kowalski"));
        assertFalse(shape.contains("1971"));
    }

    /** Same constant names as the SDK's AgeOverPossibleValues enum. */
    private enum AgeOver { NOT_RETRIEVED, FALSE, TRUE }

    @Test
    public void mapsAgeOverEnumToBooleanOrNull() {
        assertTrue(Tap2iDPayload.value(AgeOver.TRUE).getAsBoolean());
        assertFalse(Tap2iDPayload.value(AgeOver.FALSE).getAsBoolean());
        assertTrue(Tap2iDPayload.value(AgeOver.NOT_RETRIEVED).isJsonNull());
    }
}
