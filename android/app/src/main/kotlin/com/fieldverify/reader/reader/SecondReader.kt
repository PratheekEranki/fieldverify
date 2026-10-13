package com.fieldverify.reader.reader

import android.app.Activity
import android.content.Context
import android.nfc.NfcAdapter
import android.nfc.Tag
import android.nfc.tech.IsoDep
import android.os.Handler
import android.os.Looper
import android.util.Log
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeout
import kotlinx.io.bytestring.ByteString
import org.multipaz.cbor.Bstr
import org.multipaz.cbor.Cbor
import org.multipaz.cbor.DataItem
import org.multipaz.cbor.Simple
import org.multipaz.cbor.Tagged
import org.multipaz.cbor.buildCborArray
import org.multipaz.context.initializeApplication
import org.multipaz.crypto.Algorithm
import org.multipaz.crypto.AsymmetricKey
import org.multipaz.crypto.Crypto
import org.multipaz.mdoc.connectionmethod.MdocConnectionMethod
import org.multipaz.mdoc.connectionmethod.MdocConnectionMethodBle
import org.multipaz.mdoc.engagement.DeviceEngagement
import org.multipaz.mdoc.nfc.MdocReaderNfcHandoverOptions
import org.multipaz.mdoc.nfc.mdocReaderNfcHandover
import org.multipaz.mdoc.request.DeviceRequestGenerator
import org.multipaz.mdoc.response.DeviceResponseParser
import org.multipaz.mdoc.role.MdocRole
import org.multipaz.mdoc.sessionencryption.SessionEncryption
import org.multipaz.mdoc.transport.MdocTransport
import org.multipaz.mdoc.transport.MdocTransportFactory
import org.multipaz.mdoc.transport.MdocTransportOptions
import org.multipaz.mdoc.transport.NfcTransportMdocReader
import org.multipaz.nfc.NfcIsoTagAndroid
import org.multipaz.util.Constants
import org.multipaz.util.UUID
import org.multipaz.util.fromBase64Url
import kotlin.coroutines.resume

/**
 * Second, separate ISO 18013-5 read with the open-source Multipaz library (org.multipaz:multipaz 0.101.0), used only
 * to fetch name/DOB when the Tap2iD profile shares none. Tap2iD stays the source of the authenticity verdict.
 * The library checks the issuer signature, device signature, digests and validity of what it reads; the backend
 * rejects the details if any of those fail. APIs used here were read from the 0.101.0 sources jar (CONTEXT.md §12).
 * Every callback is delivered on the main thread.
 */
class SecondReader(context: Context) {

    interface Callback {
        fun onStatus(message: String)
        fun onResult(result: Result)
        fun onError(message: String)
    }

    /** What the second read returned. Values are never logged. */
    class Result(
        val docType: String,
        val givenName: String?,
        val familyName: String?,
        val birthDate: String?, // ISO yyyy-mm-dd
        val issuingAuthority: String?,
        val issuerDn: String?,
        val issuerSignedValid: Boolean,
        val deviceSignedValid: Boolean,
        val digestsValid: Boolean,
        val validNow: Boolean,
    )

    private val main = Handler(Looper.getMainLooper())
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var job: Job? = null

    init {
        initializeApplication(context.applicationContext)
    }

    /** NFC engagement (tap), then data over Bluetooth. The phones can be separated once "Connected" is shown. */
    fun readWithNfc(activity: Activity, callback: Callback) {
        cancel()
        val adapter = NfcAdapter.getDefaultAdapter(activity)
        if (adapter == null || !adapter.isEnabled) {
            callback.onError("NFC is off or missing on this phone. Use the QR option.")
            return
        }
        job = scope.launch {
            // Offer Bluetooth both ways for negotiated handover (same as the Multipaz reference reader).
            val uuid = UUID.randomUUID()
            val warm = listOf(
                MdocConnectionMethodBle(false, true, null, uuid),
                MdocConnectionMethodBle(true, false, uuid, null),
            ).map { MdocTransportFactory.Default.createTransport(it, MdocRole.MDOC_READER, MdocTransportOptions()) }
            var chosen: MdocTransport? = null
            try {
                warm.forEach { it.advertise() }
                status(callback, "Hold the phones back to back…")
                // NFC contact often drops mid-handshake (seen Oct 13: "Transceive failed"). Keep reader mode on and
                // retry on the next tap instead of failing the whole read.
                var tag: NfcIsoTagAndroid? = null
                var handover: org.multipaz.mdoc.nfc.MdocReaderNfcHandoverResult? = null
                var attempt = 0
                while (handover == null) {
                    attempt++
                    val isoDep = awaitIsoDep(activity, adapter)
                    Log.i(TAG, "Second read: NFC tag found (attempt $attempt), starting handover")
                    val t = NfcIsoTagAndroid(isoDep, Dispatchers.IO) { }
                    try {
                        handover = mdocReaderNfcHandover(
                            tag = t,
                            negotiatedHandoverConnectionMethods = warm.map { it.connectionMethod },
                            options = MdocReaderNfcHandoverOptions(useNfcV2 = false),
                        ) ?: throw IllegalStateException("The other phone didn't answer as a mobile ID.")
                        tag = t
                    } catch (e: CancellationException) {
                        throw e
                    } catch (e: Throwable) {
                        if (!isContactLost(e) || attempt >= MAX_NFC_ATTEMPTS) throw e
                        Log.w(TAG, "Second read: NFC contact lost on attempt $attempt, waiting for another tap")
                        status(callback, "Lost contact. Hold the phones together again and keep them still…")
                    }
                }
                val method = handover.connectionMethods.firstOrNull { it is MdocConnectionMethodBle }
                    ?: handover.connectionMethods.firstOrNull()
                    ?: throw IllegalStateException("The wallet offered no way to send the data.")
                Log.i(TAG, "Second read: handover ${handover.type}, methods=${handover.connectionMethods}, using $method")
                chosen = warm.firstOrNull { it.connectionMethod == method }
                    ?: MdocTransportFactory.Default.createTransport(method, MdocRole.MDOC_READER, MdocTransportOptions())
                if (chosen is NfcTransportMdocReader) chosen.setTag(tag!!)
                warm.filter { it !== chosen }.forEach { runCatching { it.close() } }
                adapter.disableReaderMode(activity)
                status(callback, "Connected. You can separate the phones; the provider approves on their phone…")
                deliver(callback, session(chosen, handover.encodedDeviceEngagement, handover.handover))
            } catch (e: CancellationException) {
                throw e
            } catch (e: Throwable) {
                fail(callback, e)
            } finally {
                runCatching { adapter.disableReaderMode(activity) }
                warm.filter { it !== chosen }.forEach { runCatching { it.close() } }
            }
        }
    }

    /** QR engagement: [qrText] is the "mdoc:…" text the wallet shows. Data goes over Bluetooth. */
    fun readWithQr(qrText: String, callback: Callback) {
        cancel()
        job = scope.launch {
            try {
                val engagement = ByteString(qrText.trim().removePrefix("mdoc:").fromBase64Url())
                val de = DeviceEngagement.fromDataItem(Cbor.decode(engagement.toByteArray()))
                val method = MdocConnectionMethod.disambiguate(de.connectionMethods, MdocRole.MDOC_READER)
                    .firstOrNull { it is MdocConnectionMethodBle }
                    ?: throw IllegalStateException("The wallet's QR code offers no Bluetooth connection.")
                val transport = MdocTransportFactory.Default.createTransport(
                    method, MdocRole.MDOC_READER, MdocTransportOptions()
                )
                status(callback, "Connecting over Bluetooth; the provider approves on their phone…")
                deliver(callback, session(transport, engagement, Simple.NULL))
            } catch (e: CancellationException) {
                throw e
            } catch (e: Throwable) {
                fail(callback, e)
            }
        }
    }

    fun cancel() {
        job?.cancel()
        job = null
    }

    /** ISO 18013-5 session: request given_name, family_name, birth_date, issuing_authority; parse and check. */
    private suspend fun session(transport: MdocTransport, engagement: ByteString, handover: DataItem): Result {
        val eDeviceKey = DeviceEngagement.fromDataItem(Cbor.decode(engagement.toByteArray())).eDeviceKey
        val eReaderKey = Crypto.createEcPrivateKey(eDeviceKey.curve)
        val sessionTranscript = Cbor.encode(buildCborArray {
            add(Tagged(Tagged.ENCODED_CBOR, Bstr(engagement.toByteArray())))
            add(Tagged(Tagged.ENCODED_CBOR, Bstr(Cbor.encode(eReaderKey.publicKey.toCoseKey().toDataItem()))))
            add(handover)
        })
        val request = DeviceRequestGenerator(sessionTranscript)
            .addDocumentRequest(
                docType = MDL_DOC_TYPE,
                itemsToRequest = mapOf(
                    MDL_NAMESPACE to mapOf(
                        "given_name" to false, "family_name" to false, "birth_date" to false,
                        "issuing_authority" to false,
                    )
                ),
                requestInfo = null,
                readerKey = null,
                signatureAlgorithm = Algorithm.UNSET,
                readerKeyCertificateChain = null,
            )
            .generate()
        val encryption = SessionEncryption(MdocRole.MDOC_READER, eReaderKey, eDeviceKey, sessionTranscript)
        try {
            withTimeout(120_000) {
                transport.open(eDeviceKey)
                transport.sendMessage(encryption.encryptMessage(request, null))
            }
            val data = withTimeout(180_000) { transport.waitForMessage() }
            if (data.isEmpty()) throw IllegalStateException("The wallet ended the session without sharing.")
            val (message, statusCode) = encryption.decryptMessage(data)
            runCatching {
                transport.sendMessage(SessionEncryption.encodeStatus(Constants.SESSION_DATA_STATUS_SESSION_TERMINATION))
            }
            if (message == null) {
                throw IllegalStateException("The provider didn't share the details (status $statusCode).")
            }
            val response = DeviceResponseParser(message, sessionTranscript)
                .setEphemeralReaderKey(AsymmetricKey.anonymous(eReaderKey))
                .parse()
            val doc = response.documents.firstOrNull()
                ?: throw IllegalStateException("The wallet shared no document.")
            fun text(name: String): String? = runCatching {
                Cbor.decode(doc.getIssuerEntryData(MDL_NAMESPACE, name)).asTstr
            }.getOrNull()
            val birthDate = runCatching {
                Cbor.decode(doc.getIssuerEntryData(MDL_NAMESPACE, "birth_date")).asDateStringOrDateTimeString.toString()
            }.getOrNull()
            val now = System.currentTimeMillis()
            val validNow = runCatching {
                now >= doc.validityInfoValidFrom.toEpochMilliseconds() &&
                    now <= doc.validityInfoValidUntil.toEpochMilliseconds()
            }.getOrDefault(false)
            val issuerDn = runCatching { doc.issuerCertificateChain.certificates.first().issuer.name }.getOrNull()
            return Result(
                docType = doc.docType,
                givenName = text("given_name"),
                familyName = text("family_name"),
                birthDate = birthDate,
                issuingAuthority = text("issuing_authority"),
                issuerDn = issuerDn,
                issuerSignedValid = doc.issuerSignedAuthenticated,
                deviceSignedValid = doc.deviceSignedAuthenticated,
                digestsValid = doc.numIssuerEntryDigestMatchFailures == 0,
                validNow = validNow,
            )
        } finally {
            runCatching { transport.close() }
        }
    }

    /** Waits for the next ISO-DEP (NFC) tag using Android reader mode on [activity]. */
    private suspend fun awaitIsoDep(activity: Activity, adapter: NfcAdapter): IsoDep =
        suspendCancellableCoroutine { cont ->
            val flags = NfcAdapter.FLAG_READER_NFC_A or NfcAdapter.FLAG_READER_NFC_B or
                NfcAdapter.FLAG_READER_SKIP_NDEF_CHECK
            adapter.enableReaderMode(activity, { tag: Tag ->
                val isoDep = IsoDep.get(tag)
                if (isoDep != null && cont.isActive) {
                    runCatching {
                        isoDep.connect()
                        isoDep.timeout = 20_000
                    }
                    cont.resume(isoDep)
                }
            }, flags, null)
            cont.invokeOnCancellation { runCatching { adapter.disableReaderMode(activity) } }
        }

    private fun status(callback: Callback, message: String) {
        Log.i(TAG, "Second read: $message")
        main.post { callback.onStatus(message) }
    }

    private fun deliver(callback: Callback, result: Result) {
        // Shape and checks only, never values.
        Log.i(TAG, "Second read result: doc=${result.docType} issuerSigned=${result.issuerSignedValid} " +
            "deviceSigned=${result.deviceSignedValid} digests=${result.digestsValid} validNow=${result.validNow} " +
            "given=${result.givenName != null} family=${result.familyName != null} dob=${result.birthDate != null} " +
            "issuer=${result.issuingAuthority != null} dn=${result.issuerDn}")
        main.post { callback.onResult(result) }
    }

    private fun isContactLost(t: Throwable): Boolean =
        t is java.io.IOException || t is org.multipaz.nfc.NfcTagLostException ||
            t.message?.contains("Transceive failed") == true || t.message?.contains("Tag was lost") == true

    private fun fail(callback: Callback, t: Throwable) {
        Log.w(TAG, "Second read failed", t)
        val message = if (isContactLost(t)) {
            "The phones lost contact. Tap again and keep them still until it says Connected, or use the QR option."
        } else {
            t.message?.takeIf { it.isNotBlank() } ?: t.javaClass.simpleName
        }
        main.post { callback.onError(message) }
    }

    companion object {
        const val MDL_DOC_TYPE = "org.iso.18013.5.1.mDL"
        const val MDL_NAMESPACE = "org.iso.18013.5.1"
        const val READER_NAME = "multipaz-0.101.0"
        private const val MAX_NFC_ATTEMPTS = 5
        private const val TAG = "FieldVerify"
    }
}
