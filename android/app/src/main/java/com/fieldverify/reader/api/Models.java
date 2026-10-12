package com.fieldverify.reader.api;

import java.util.Collections;
import java.util.List;
import java.util.Map;

/**
 * Mirrors of the backend's response models (backend/app/schemas.py). Gson maps snake_case JSON to these
 * camelCase fields (see BackendClient). Only the fields the app shows are declared.
 */
public final class Models {

    private Models() {
    }

    public static class ProviderSummary {
        public long id;
        public String name;
        public String npi;
        public String specialty;
        public String riskLevel;
    }

    public static class Visit {
        public long id;
        public String scheduledAt; // ISO local date-time, e.g. 2026-10-12T09:30:00
        public String siteAddress;
        public String status;
        public String visitType;
        public ProviderSummary provider;
    }

    public static class Authenticity {
        public String status; // verified / failed / not_checked
        public Map<String, Boolean> checks = Collections.emptyMap();
        public String issuer;
    }

    public static class FieldResult {
        public String field;
        public String result;
        public double points;
        public int max;
        public String reason;
    }

    public static class Match {
        public int score;
        public String band; // green / yellow / red
        public boolean insufficientData;
        public int providedWeight;
        public String hardRule;
        public List<String> caps = Collections.emptyList();
        public List<FieldResult> fields = Collections.emptyList();
    }

    public static class Outcome {
        public String label;
        public String color;
    }

    public static class VerificationResult {
        public String id;
        public long visitId;
        public String visitType;
        public ProviderSummary provider;
        public String mode;
        public String channel;
        public String flow;
        public Authenticity authenticity;
        public Match match;
        public Outcome outcome;
        public Boolean photoChecked;
        public String portraitDataUrl;
        public Map<String, Boolean> attributes = Collections.emptyMap();
        public String matchSource; // wallet / id_details / manual / none
        public String supplements;
        public boolean saved;

        /** Genuine credential that shared no name/DOB (age-check profile): finish with the physical ID's details. */
        public boolean needsIdDetails() {
            return "digital".equals(mode) && authenticity != null && "verified".equals(authenticity.status)
                    && "none".equals(matchSource);
        }
    }

    public static class AuditEntry {
        public long id;
        public String outcome;
        public String entryHash;
    }
}
