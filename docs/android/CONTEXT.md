# Android reader: verified context

**Read this before writing or changing any Android code.** It lists only facts that were checked against a source,
with the source named. If something you need isn't here, it is **unknown**: find it in the real SDK artifact (see
§9) or on a device, add it here with its source, and only then write the code. Do not guess SDK APIs.

Last verified: Oct 12 2026, against `com.credenceid:tap2idSdk:2.0.0` (AAR downloaded from Credence's Maven repo and
inspected with `javap`), the Credence Android docs, and the backend in this repo.

---

## 1. What the Android app is (ADR-0006)

A second front end for FieldVerify. The auditor's Android phone reads the provider's mobile driver's license in person
(NFC tap or QR) with Credence's **Tap2iD SDK**, then sends the result to the **same FastAPI backend** the web app uses.
The backend scores it against the enrollment record and writes the audit log. **The app holds no scoring, outcome or
audit logic.**

- Language: **Java**, plus two thin **Kotlin** files: `Tap2iDVerifier.kt` (wraps the Tap2iD SDK's `suspend` functions)
  and `SecondReader.kt` (the optional open-source second read, §12 / ADR-0008).
- Package / applicationId: **`com.fieldverify.reader`** (the Tap2iD evaluation license is bound to this exact id).
- Hard stop: Tue Oct 13, 8:00 PM CT (ADR-0006). If not working end to end, it is not submitted.

## 2. Rules for any agent working here

1. Use only the SDK signatures in §4. They come from the compiled artifact, not the web docs (which are wrong in places, §5).
2. Do **not** copy code from Credence's `Tap2iD-SDK-Android` sample repo (license forbids reuse). Reading it is fine.
3. Secrets (`TAP2ID_API_KEY`, `DEVICE_TOKEN`) go in `android/local.properties` (gitignored), never in source.
4. Never log attribute values (names, DOB, portrait). Log keys and types only.
5. All Java except `Tap2iDVerifier.kt` and `SecondReader.kt`. Keep them thin bridges: no scoring or outcome logic.
6. The app never decides "verified". It sends Credence's raw check results; the backend computes authenticity (§7).

## 3. Toolchain and dependency facts

| Fact | Value | Source |
|---|---|---|
| Maven repo | `https://nexus.credenceid.com/repository/credenceid-sdk-group/` (open, **no credentials**; metadata/AAR/POM return 200 anonymously) | Integration page; checked with curl Oct 12 |
| Artifact | `com.credenceid:tap2idSdk:2.0.0` (AAR, 125 KB) | Integration page; repo |
| Other versions | 1.0.x, **2.2.0** (stable), 2.1/2.2.x RCs; latest `2.2.1-RC3` | `maven-metadata.xml` |
| 2.2.0 vs 2.0.0 | Same API plus `refreshConfiguration()` and `verifyPdf417(...)`. Additive only. | `javap` diff |
| minSdk | **29** (Android 10) | SDK `AndroidManifest.xml`, docs |
| SDK Kotlin stdlib | `org.jetbrains.kotlin:kotlin-stdlib:2.3.0` → use **Kotlin Gradle plugin 2.3.x** | SDK POM |
| SDK runtime deps | `c-identity`, `c-identity-android`, `c-identity-utils` (`2.0.0-Sdk`, same repo), androidx core-ktx 1.17.0, appcompat 1.7.1, material 1.13.0, koin-android 4.1.1, rxjava 2.2.21, rxandroid 2.1.1, `com.github.Akaizz.Fetch:fetch2:3.3`, kronos-android 0.0.1-alpha11 | SDK POM |
| JDK | 17 (Gradle JDK in Android Studio; machine default can stay 21) | Integration page |
| Gradle wrapper | 8.14.3 | Integration page |
| Android Studio | "Panda 4" or later (candidate has 2026.2.1) | Integration page |
| compileSdk / targetSdk / AGP | **36 / 36 / AGP 8.13.2**, Kotlin plugin **2.3.21**, Gradle 8.14.3. Clean `assembleDebug` + unit tests passed with SDK 2.0.0. (AGP 9.x needs Gradle 9; not used.) | Build, Oct 12 |
| Extra repository | **JitPack** (`https://jitpack.io`), only for `com.github.Akaizz.Fetch:fetch2:3.3`; it is not on Credence's Nexus or Maven Central | Build + curl, Oct 12 |
| Coroutines | Arrive transitively (`kotlinx-coroutines-rx2` via `c-identity-utils`); we also declare `kotlinx-coroutines-android` 1.10.2 for `Dispatchers.Main` | `c-identity-utils` POM |
| Material 3 theme | `Theme.Material3.Light` (there is no `Theme.Material3.Light.DarkActionBar`) | Build error, Oct 12 |
| 16 KB page size | SDK pulls `androidx.datastore` 1.2.0, whose `libdatastore_shared_counter.so` RELRO isn't 16 KB aligned (Android 16+ debug warning). `app/build.gradle` constrains `datastore-core-android` to **1.2.1** (aligned; checked with `readelf -lW`) | Oct 13 |
| Debug APK size | ~40 MB (BouncyCastle, Guava, Room etc. come with the SDK) | Build |

## 4. Public SDK API (from the 2.0.0 artifact via `javap`)

Package roots: `com.credenceid.tap2idSdk.api`, `...api.models`, `...core.model`.

```kotlin
object Tap2iDSdk {                                         // Java: Tap2iDSdk.INSTANCE
    suspend fun initSdk(config: SdkConfig, listener: InitSdkResultListener)
    suspend fun verifyMdoc(engagementConfig: EngagementConfig, listener: MdocVerificationListener)
    fun getSdkVersion(): String
}

interface InitSdkResultListener {
    fun onInitializationSuccess(result: SdkInitializationResult)
    fun onInitializationFailure(error: java.lang.Error)    // note: Error, not Throwable
}

interface MdocVerificationListener {
    fun onVerificationStageStarted(stage: VerificationStage)
    fun onVerificationStageError(stage: VerificationStage, error: Throwable)
    fun onVerificationStageCompleted(stage: VerificationStage)
    fun onVerificationCompleted(result: com.credenceid.tap2idSdk.core.model.VerificationResult)
}

// api.models
data class SdkConfig(val apiKey: String, val applicationContext: Context)
class SdkConfigBuilder { setApiKey(String); setApplicationContext(Context); build(): SdkConfig }
data class SdkInitializationResult(val licenseVerificationResult: LicenseKeyVerificationResult)
data class LicenseKeyVerificationResult(val isValid: Boolean, val expiryDate: Long?, val profileName: String?)
data class EngagementConfig(val qrConfig: QrConfig? = null, val nfcConfig: NfcConfig? = null)
data class QrConfig(val mDocString: String)
data class NfcConfig(val activity: Activity)
enum class VerificationStage { NFC_ENGAGEMENT, QR_ENGAGEMENT, CONNECTION, SEND_MDOC_REQUEST, PARSE_MDOC_RESPONSE }

// core.model
data class VerificationResult(val documents: List<VerifiedDocument>, val status: VerificationStatus)
enum class VerificationStatus { SUCCESS, PARTIAL_SUCCESS, FAILURE }
data class VerifiedDocument(val docType: String, val nameSpaces: List<VerifiedNamespace>, val authentication: AuthenticationResult)
data class VerifiedNamespace(val name: String, val attributes: Map<String, Any?>)
data class AuthenticationResult(
    val securityChecks: SecurityChecks, val msoValidity: MsoValidity,
    val trustAttributes: TrustAttributes, val validationErrors: List<String>) {
    val authenticationStatus: AuthenticationStatus        // getter
}
enum class AuthenticationStatus { SUCCESS, WARNING, FAILURE, UNKNOWN }
data class SecurityChecks(val isIssuerSignedValid: Boolean, val isDeviceSignedValid: Boolean, val areDigestsValid: Boolean)
data class TrustAttributes(val isIssuerTrusted: Boolean, val chainStatus: TrustStatus, val issuerDistinguishedName: String?)
enum class TrustStatus { VERIFIED, EXPIRED, UNTRUSTED }
data class MsoValidity(val status: MsoStatus, val signTimestamp: Long?, val validFrom: Long?, val validUntil: Long?)
enum class MsoStatus { VALID, NOT_YET_VALID, EXPIRED, UNKNOWN }
```

Java getter names follow Kotlin rules: `getDocuments()`, `getStatus()`, `getDocType()`, `getNameSpaces()`,
`getAttributes()`, `getAuthentication()`, `getSecurityChecks()`, `isIssuerSignedValid()`, `isDeviceSignedValid()`,
`getAreDigestsValid()`, `getTrustAttributes()`, `isIssuerTrusted()`, `getChainStatus()`,
`getIssuerDistinguishedName()`, `getMsoValidity()`, `getValidationErrors()`.

There is also a class `core.model.MdocAttributes` with typed getters (`getGivenNames()`, `getFamilyName()`,
`getBirthDate(): java.time.LocalDate`, `getPortrait(): byte[]`, `isAgeOver21()`, ...), but **`VerificationResult` does
not contain it** in 2.0.0, and no public factory to build it was found. Don't rely on it.

## 5. Where the web docs are wrong for 2.0.0

| Docs say | Artifact actually has | Consequence |
|---|---|---|
| Integration page: `SdkConfig(apiKey, transport = TransportType.BLE)`, listener `onSuccess()` / `onError(String)` | `SdkConfig(apiKey, applicationContext)`; `onInitializationSuccess(SdkInitializationResult)` / `onInitializationFailure(Error)`; no `TransportType` class | Integration-page code doesn't compile |
| API reference: `VerificationResult` has `mdocAttributes`, `isIssuerSignedAuthenticated`, `isDeviceSignedAuthenticated`, `issuerInfo`, `isIssuerVerified`, `isMsoSigned`, `validationErrors` | `VerificationResult(documents, status)`; checks are per document in `AuthenticationResult` (§4) | Doc-based result handling doesn't compile |
| API reference matches for `initSdk`, `verifyMdoc`, `EngagementConfig`, `QrConfig`, `NfcConfig`, listener method names | Same | OK to use |

## 6. Permissions

Merged automatically from `c-identity-android` (its manifest):
`BLUETOOTH` (maxSdk 30), `BLUETOOTH_ADMIN` (maxSdk 30), `BLUETOOTH_SCAN` (`neverForLocation`), `BLUETOOTH_ADVERTISE`,
`BLUETOOTH_CONNECT`. So data retrieval uses **BLE** after NFC/QR engagement (ISO 18013-5).

The app must add: `INTERNET` (license check + backend), `NFC`; `<uses-feature android:name="android.hardware.nfc"
android:required="false"/>`; for QR engagement, `CAMERA` only if we scan with the camera ourselves.

**Runtime:** on Android 12+ (API 31+), request `BLUETOOTH_SCAN`, `BLUETOOTH_CONNECT`, `BLUETOOTH_ADVERTISE` before
`verifyMdoc`. (On API 29–30, BLE scanning needs location permission; the library caps legacy permissions at 30. Test on
the actual phone.)

## 7. Mapping a Tap2iD result to FieldVerify

The app sends **raw** facts; the backend decides. Backend rule (`POST /api/verify/digital/tap2id`):

```
authenticity = "verified" if
    result.status == SUCCESS
    and for the chosen document:
        securityChecks.issuerSignedValid and securityChecks.deviceSignedValid and securityChecks.digestsValid
        and trustAttributes.issuerTrusted and trustAttributes.chainStatus == VERIFIED
        and msoValidity.status == VALID
        and validationErrors is empty
  else "failed"
```
Chosen document: the first with `docType == "org.iso.18013.5.1.mDL"`, else the first document.

**Attributes:** keys are ISO 18013-5 element identifiers (`given_name`, `family_name`, `birth_date`, `portrait`,
`issuing_authority`, `age_over_21`, `resident_address`, `document_number` all appear as strings in Credence's
`c-identity` library). **Value types in the map are unknown.** The Kotlin bridge converts generically:
`String` → as is, `java.time.LocalDate` / `LocalDateTime` → ISO string, `byte[]` → base64, `Boolean`/`Number` → JSON
scalar, anything else → `toString()`. The backend already normalizes namespaced maps and ISO/AAMVA names.

**First real result (Oct 13, NFC, Multipaz Test App → Erika's visit on Render):** end to end worked. Checks:
issuerSigned ✓, deviceSigned ✓, digests ✓, MSO valid ✓, no validation errors ✓, **issuerTrusted ✗, chain ✗** (Multipaz
test IACA "C=US,CN=OWF Multipaz TEST IACA" is not in Credence's trust list) → backend "failed" → red "Credential failed
verification: escalate". Shared: `issuing_authority` ("Utopia Department of Motor Vehicles"). Not shared: name, DOB
(Age Check Profile 2.0). Portrait and `age_over_21` did not show at first; the logcat shape line explained why:

```
Tap2iD result shape: status=PARTIAL_SUCCESS | doc=org.iso.18013.5.1.mDL auth=WARNING
  ns=org.iso.18013.5.1 {issuing_authority:String portrait:Bitmap age_over_21:AgeOverPossibleValues }
```
- `portrait` is an **`android.graphics.Bitmap`** (not `byte[]`) → the app now JPEG-encodes it (quality 90) → base64.
- `age_over_NN` is **`com.credenceid.identity.iso18013.AgeOverPossibleValues`**, an enum `{NOT_RETRIEVED, FALSE, TRUE}`
  (in `c-identity`) → the app maps TRUE/FALSE to JSON booleans, NOT_RETRIEVED to null (matched by enum name).
- With an untrusted issuer the SDK reports `status=PARTIAL_SUCCESS` and `AuthenticationStatus.WARNING`.
- "Transceive failed" at NFC_ENGAGEMENT = the NFC link dropped (phones moved); hold still until stages finish.
- Seen Oct 13 after the fix: photo and "Age over 21: Yes" display. The portrait carries a **"CREDENCE ID" watermark**
  added by the SDK (not by our code; likely the evaluation license).
- NFC is flaky in practice: 8 of 10 attempts hit "Transceive failed". Also seen: `SEND_MDOC_REQUEST` error
  "[CODE :216] Please provide consent to share driving license data" (holder didn't approve/enter PIN in time).
  `VerifyActivity.friendlyError` maps Transceive failed / CODE 216 / 6A82 to plain-English messages.
- No consent/read timeout is configurable: no timeout parameter in the public API of 2.0.0 or 2.2.0 (`javap`); the
  limit lives inside the SDK/wallet. Workaround: NFC is only the engagement step; data moves over BLE, so the phones
  can be separated once NFC_ENGAGEMENT completes and the holder approves (PIN 1111 + fingerprint: Multipaz test docs
  require passphrase **and** user auth, `setUserAuthenticationRequired(true, PASSCODE|BIOMETRIC)`). QR engagement avoids
  holding phones entirely.

## 8. Backend contract (implemented in `backend/app/routers/verify_digital.py`)

`POST /api/verify/digital/tap2id`, header `X-Device-Token: <ANDROID_DEVICE_TOKEN>` (401 if wrong; 503 if the server
has no token set).

```json
{
  "visit_id": 1,
  "sdk_version": "2.0.0",
  "status": "SUCCESS",
  "documents": [{
    "doc_type": "org.iso.18013.5.1.mDL",
    "issuer_signed_valid": true, "device_signed_valid": true, "digests_valid": true,
    "issuer_trusted": true, "chain_status": "VERIFIED", "mso_status": "VALID",
    "issuer_dn": "CN=...", "validation_errors": [],
    "namespaces": { "org.iso.18013.5.1": { "given_name": "…", "family_name": "…", "birth_date": "1971-04-12",
                                           "portrait": "<base64>", "age_over_21": true } }
  }]
}
```
Returns the same `VerificationResult` JSON as the web flow (`mode: digital`, `channel: android`, `flow: tap2id`).
Then `POST /api/audit` with `result_id` saves it. Other endpoints the app uses: `GET /api/visits`,
`GET /api/visits/{id}`, `GET /api/health`.

Trust note (say this in Q&A): the backend can't re-check Tap2iD's cryptography, which ran on the phone. The
prototype authenticates the device with a shared token; production would use Play Integrity attestation or mTLS.

## 8b. Where things are in `android/`

| File | Role |
|---|---|
| `app/src/main/kotlin/.../reader/Tap2iDVerifier.kt` | The only Kotlin file: `initSdk` / `verifyMdoc` → Java callbacks on the main thread |
| `app/src/main/java/.../reader/Tap2iDPayload.java` | SDK `VerificationResult` → §8 JSON; generic attribute conversion; shape-only log line |
| `app/src/main/java/.../api/BackendClient.java`, `Models.java` | OkHttp + Gson (snake_case ↔ camelCase); errors parsed from `{"error": {"message"}}` |
| `app/src/main/java/.../ui/*Activity.java` | Visits → Verify (permissions, NFC/QR, stages) → Result (two signals, age-check completion, save) |
| `app/src/test/.../Tap2iDPayloadTest.java` | Builds results with the SDK's public model constructors |
| `local.properties` (gitignored) | `TAP2ID_API_KEY`, `BACKEND_URL`, `DEVICE_TOKEN` → `BuildConfig` |

Not yet observed on a device (keep in mind when debugging): whether `onVerificationCompleted` is also called after a
stage error, whether cancelling the coroutine tears down the SDK's NFC/BLE session, and the exact QR text format
(the app accepts text starting with `mdoc:`).

## 8c. Test wallet and demo records

- Test holder: **Multipaz Test App** (https://apps.multipaz.org). Document Store → "Create Test Documents in Software
  Secure Area". Its driving licenses are all the same synthetic person: **Erika Mustermann, 1971-09-01**, issued by
  "Utopia Department of Motor Vehicles" (`SampleData.kt` in the Multipaz repo). No custom names.
- Present by NFC from the start screen, or "ISO mdoc Proximity Sharing" → "Present mDL via QR".
- When sharing, the holder phone asks for the document PIN: **1111** (hardcoded for Software Secure Area test
  documents in `DocumentStoreScreen.kt`: `setPassphraseRequired(true, "1111", PIN_FOUR_DIGITS)`).
- Seeded visits for that ID (backend/app/seed.py): **Erika Mustermann** → green; **Erica Musterman** (misspelled
  enrollment, same DOB) → yellow, score 73; any other visit (e.g. Robert Kowalski) → red "different person".
- Its issuer certificate is a test one: expect `issuer_trusted=false` unless added to Credence Trust Management. The IACA
  key is bundled but the certificate is generated on first launch (random serial, `App.kt` `iacaInit`), so it must be
  exported from that phone to be trusted; there is no fixed file to upload.

## 9. How to re-verify an SDK fact

```bash
R=https://nexus.credenceid.com/repository/credenceid-sdk-group/com/credenceid/tap2idSdk/2.0.0
curl -sO $R/tap2idSdk-2.0.0.aar && unzip -o tap2idSdk-2.0.0.aar classes.jar && mkdir c && cd c && unzip -q ../classes.jar
javap -public -cp . com.credenceid.tap2idSdk.core.model.VerificationResult
```

## 10. Licensing and profile

- Evaluation license for **`com.fieldverify.reader`** (Android, In-person SDK) → `TAP2ID_API_KEY` in `.env`; copy to
  `android/local.properties`. Expires 2027-01-07.
- `LicenseKeyVerificationResult.profileName` tells which Credence profile governs requested fields. Observed Oct 12:
  **`Age Check Profile 2.0`** (same profile family as the Cloud SDK web flow). Expect issuer + portrait + `age_over_NN`,
  and probably no name/DOB → the backend returns yellow "compare the photo" and the Result screen offers the
  "Complete the record check" step (ADR-0007). Confirm the actual fields with the first real read (§7).

## 11. Open questions (answer on a real device, then record here)

| # | Question | Status |
|---|---|---|
| 1 | Does `initSdk` succeed with our key + package, and what `profileName` comes back? | **answered Oct 12**: success on an API 37 emulator; `getSdkVersion()` = `2.0.0`, `profileName` = `Age Check Profile 2.0` |
| 2 | Attribute value types in `VerifiedNamespace.attributes` (String? LocalDate? byte[]?) | **answered Oct 13** (§7): String, `Bitmap` (portrait), `AgeOverPossibleValues` enum (age_over_NN). Name/DOB types still unseen (not shared by the Age Check profile). |
| 3 | Can the candidate's wallet ID (Google Wallet ID pass?) present in person to a Tap2iD reader at all? | **Oct 12, first try failed**: `NFC_ENGAGEMENT` stage error "Engagement failed … APDU status is: 6A82, expected 9000". 6A82 = ISO 7816 "file or application not found": the other phone answered NFC but has no mdoc engagement app selected (wallet not presenting, or that ID/wallet doesn't support in-person tap to third-party readers). App + SDK side worked (NFC field up, reader talked to the phone). **Cause confirmed: the second phone had no mobile ID on it.** Plan: install the open-source **Multipaz Test App** (OpenWallet Foundation, APKs at https://apps.multipaz.org) on the second Android phone as a test holder. Its test IACA isn't in Credence's trust list, so expect `issuer_trusted=false` → authenticity failed unless that IACA is added in the portal's Trust Management. |
| 4 | Which runtime permissions are actually prompted on the test phone's Android version | open |
| 5 | compileSdk / AGP versions that build cleanly with SDK 2.0.0 | **answered**: §3 |

## 12. Second read for name/DOB (open-source, ADR-0008)

Library: **`org.multipaz:multipaz:0.101.0`** (Maven Central; Kotlin Multiplatform, Android variant
`multipaz-android`, kotlin-stdlib 2.2.21). APIs below were read from `multipaz-android-0.101.0-sources.jar`, not from
the GitHub main branch (main has newer APIs such as `VerificationSession`; don't copy from it).

| Need | 0.101.0 API used |
|---|---|
| App context | `org.multipaz.context.initializeApplication(applicationContext)` (must run before BLE transports) |
| NFC tag | Android `NfcAdapter.enableReaderMode` → `IsoDep` → `NfcIsoTagAndroid(isoDep, Dispatchers.IO) { }` (public). The library's own `NfcTagReader.scan` needs its Compose prompt UI, so it's not used |
| NFC handover | `mdocReaderNfcHandover(tag, negotiatedHandoverConnectionMethods, MdocReaderNfcHandoverOptions(useNfcV2 = false))` → `encodedDeviceEngagement`, `handover`, `connectionMethods` |
| QR engagement | `"mdoc:" + base64url(DeviceEngagement)`; handover = `Simple.NULL`; `MdocConnectionMethod.disambiguate(…, MdocRole.MDOC_READER)` |
| Transport | `MdocTransportFactory.Default.createTransport(method, MdocRole.MDOC_READER, MdocTransportOptions())`; `advertise()`, `open(eDeviceKey)`, `sendMessage`, `waitForMessage`, `close()` |
| Session | `SessionTranscript = [24(DeviceEngagement), 24(EReaderKey COSE), handover]`; `SessionEncryption(MdocRole.MDOC_READER, eReaderKey, eDeviceKey, transcript)`; `encryptMessage(msg, null)`, `decryptMessage(data)` → `(ByteArray?, Long?)` |
| Request | `DeviceRequestGenerator(transcript).addDocumentRequest(docType, itemsToRequest, null, null, Algorithm.UNSET, null).generate()` (unsigned request) |
| Response | `DeviceResponseParser(bytes, transcript).setEphemeralReaderKey(AsymmetricKey.anonymous(eReaderKey)).parse()` → `documents[0]`: `issuerSignedAuthenticated`, `deviceSignedAuthenticated`, `numIssuerEntryDigestMatchFailures`, `validityInfoValidFrom/Until`, `issuerCertificateChain`, `getIssuerEntryData(ns, name)` (CBOR; `birth_date` via `asDateStringOrDateTimeString`) |

Backend: `POST /api/verify/digital/second-read` (`X-Device-Token`). Body: `result_id`, `reader`, `doc_type`,
`issuer_signed_valid`, `device_signed_valid`, `digests_valid`, `valid_now`, `issuer_dn`, `issuing_authority`,
`given_name`, `family_name`, `birth_date`. Rejects (422) if any check is false or name/DOB missing; 409 if the issuing
authority differs from the first read or the result isn't a Tap2iD result with `match_source="none"`. Result:
`match_source="second_read"`, outcome capped at yellow, authenticity unchanged. Tests: `backend/tests/test_second_read.py`.

Known limits: no cryptographic link between the two reads (issuer equality is only a sanity check); the second read's
issuer isn't trust-checked; reader request is unsigned (no reader authentication), which Multipaz accepts because its
"Configure Reader Identifiers" list is empty. **Untested on devices as of Oct 13 12:05; the app builds.**

Expected with the Multipaz test ID on Erika's visit: first read red (untrusted test issuer); second read fills
Erika / Mustermann / 1971-09-01 → match green 100, overall stays red. On a genuine trusted ID the overall would be
yellow ("not checked by Credence: confirm").

## Sources
- Android API reference: https://credenceid.com/mobile-id/developer-documentation/tap2id/android/using-the-sdk/
- Android integration: https://credenceid.com/mobile-id/developer-documentation/tap2id/android/integration/
- Artifact + POM: `https://nexus.credenceid.com/repository/credenceid-sdk-group/com/credenceid/tap2idSdk/2.0.0/`
- Identity library manifest: `.../com/credenceid/c-identity-android/2.0.0-Sdk/c-identity-android-2.0.0-Sdk.aar`
- FieldVerify decisions: `docs/decisions/0006-one-backend-two-front-ends.md`, `0007-age-check-profile-completion.md`, `0008-android-second-read.md`
- Multipaz 0.101.0 sources: `https://repo1.maven.org/maven2/org/multipaz/multipaz-android/0.101.0/multipaz-android-0.101.0-sources.jar`
