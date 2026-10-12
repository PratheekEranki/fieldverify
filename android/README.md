# FieldVerify Reader (Android)

In-person mobile ID check for Medicaid site visits. The auditor's phone reads the provider's mobile driver's license
with Credence ID's **Tap2iD SDK** (NFC tap or wallet QR code). The app then sends the raw result to the same FieldVerify
backend the web app uses, which checks authenticity, scores the match against the enrollment record and writes the
audit log.

Read [`../docs/android/CONTEXT.md`](../docs/android/CONTEXT.md) before changing anything here. It holds the verified
SDK API and the backend contract.

## What's in it

| Path | What it does |
|---|---|
| `app/src/main/kotlin/.../reader/Tap2iDVerifier.kt` | The only Kotlin file. Bridges the SDK's `suspend` calls to Java callbacks. |
| `app/src/main/java/.../reader/Tap2iDPayload.java` | Turns a Tap2iD `VerificationResult` into the backend's JSON. Raw checks only, no verdict. |
| `app/src/main/java/.../api/BackendClient.java` | OkHttp + Gson client for `/api/visits`, `/api/verify/digital/tap2id`, `/supplement`, `/api/audit`. |
| `app/src/main/java/.../ui/MainActivity.java` | Today's visits and the reader's license status. |
| `app/src/main/java/.../ui/VerifyActivity.java` | Permissions, NFC or QR engagement, stage progress, submit. |
| `app/src/main/java/.../ui/ResultActivity.java` | The two signals (genuine? matches record?), age-check completion, save to audit log. |
| `app/src/test/.../Tap2iDPayloadTest.java` | JVM tests built from the SDK's own model classes. |

## Toolchain (verified by a clean build, Oct 12 2026)

- Android Gradle Plugin 8.13.2, Gradle 8.14.3 (wrapper included), Kotlin plugin 2.3.21
- compileSdk / targetSdk 36, minSdk 29 (the SDK's minimum)
- Java 17 bytecode. Builds on JDK 17 or 21.
- Repositories: Google, Maven Central, Credence's Nexus (no login), JitPack (one SDK dependency lives only there)

## Setup

1. Copy `local.properties.example` to `local.properties` and fill it in:
   - `TAP2ID_API_KEY`: the In-person SDK key for `com.fieldverify.reader`, from the repo-root `.env`.
   - `DEVICE_TOKEN`: any long random string. Set the same value as `ANDROID_DEVICE_TOKEN` on the backend (Render
     environment, or `.env` locally).
   - `BACKEND_URL`: defaults to the Render deployment.
2. Open the `android/` folder in Android Studio. It adds `sdk.dir` to `local.properties` and syncs Gradle.
3. Plug in an Android 10+ phone with NFC and Bluetooth, then Run. Or from a terminal:

```powershell
cd android
.\gradlew.bat :app:installDebug
.\gradlew.bat :app:testDebugUnitTest
```

## Using it

1. The top bar should say **Mobile ID reader ready**. If it says unavailable, the license check failed (wrong key,
   wrong package, or no internet). Tap it to retry.
2. Pick a visit, then **Tap phones (NFC)** or **Scan wallet QR code**. Allow Nearby devices (and the camera for QR).
3. The provider approves the request in their wallet. The result screen shows whether the ID is genuine and whether
   it matches the record. For an age-check credential (no name or DOB shared), confirm the photo and enter the details
   printed on the ID.
4. **Save to audit log.** The entry shows up in the web app's audit log with channel `android`.

## Logs

`adb logcat -s FieldVerify` shows the stage errors and, after a successful read, the result's shape (document type,
namespaces, attribute keys and value classes). It never logs values. Copy that shape line into CONTEXT.md §7.
