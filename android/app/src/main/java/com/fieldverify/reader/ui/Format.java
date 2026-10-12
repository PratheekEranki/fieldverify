package com.fieldverify.reader.ui;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.Locale;

/** Small display helpers shared by the screens. */
final class Format {

    private static final DateTimeFormatter TIME = DateTimeFormatter.ofPattern("h:mm a", Locale.US);

    private Format() {
    }

    static String visitTime(String isoLocalDateTime) {
        if (isoLocalDateTime == null) {
            return "";
        }
        try {
            String trimmed = isoLocalDateTime.length() > 19 ? isoLocalDateTime.substring(0, 19) : isoLocalDateTime;
            return LocalDateTime.parse(trimmed).format(TIME);
        } catch (DateTimeParseException e) {
            return isoLocalDateTime;
        }
    }

    /** "id_details" -> "Id details", "high" -> "High". */
    static String title(String value) {
        if (value == null || value.isEmpty()) {
            return "";
        }
        String spaced = value.replace('_', ' ');
        return Character.toUpperCase(spaced.charAt(0)) + spaced.substring(1);
    }

    /** "issuerSignedValid" -> "Issuer signed valid". */
    static String checkName(String camel) {
        StringBuilder sb = new StringBuilder();
        for (char c : camel.toCharArray()) {
            if (Character.isUpperCase(c) && sb.length() > 0) {
                sb.append(' ').append(Character.toLowerCase(c));
            } else {
                sb.append(c);
            }
        }
        return title(sb.toString());
    }

    static String fieldName(String field) {
        switch (field) {
            case "last_name":
                return "Last name";
            case "first_name":
                return "First name";
            case "dob":
                return "Date of birth";
            case "ssn":
                return "SSN";
            case "address":
                return "Address";
            default:
                return title(field);
        }
    }

    static String points(double points, int max) {
        String p = points == Math.rint(points) ? String.valueOf((int) points) : String.format(Locale.US, "%.1f", points);
        return p + "/" + max;
    }
}
