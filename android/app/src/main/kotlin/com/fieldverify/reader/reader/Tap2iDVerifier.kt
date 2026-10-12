package com.fieldverify.reader.reader

import android.app.Activity
import android.content.Context
import android.os.Handler
import android.os.Looper
import com.credenceid.tap2idSdk.api.InitSdkResultListener
import com.credenceid.tap2idSdk.api.MdocVerificationListener
import com.credenceid.tap2idSdk.api.Tap2iDSdk
import com.credenceid.tap2idSdk.api.models.EngagementConfig
import com.credenceid.tap2idSdk.api.models.LicenseKeyVerificationResult
import com.credenceid.tap2idSdk.api.models.NfcConfig
import com.credenceid.tap2idSdk.api.models.QrConfig
import com.credenceid.tap2idSdk.api.models.SdkConfig
import com.credenceid.tap2idSdk.api.models.SdkInitializationResult
import com.credenceid.tap2idSdk.api.models.VerificationStage
import com.credenceid.tap2idSdk.core.model.VerificationResult
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/**
 * The only Kotlin file in the app: a thin bridge from the Tap2iD SDK's `suspend` functions to plain Java callbacks.
 * No business logic here. Every callback is delivered on the main thread.
 * SDK signatures used here are the ones read from the 2.0.0 artifact (docs/android/CONTEXT.md §4).
 */
class Tap2iDVerifier(context: Context) {

    interface InitCallback {
        fun onReady(license: LicenseKeyVerificationResult)
        fun onFailed(message: String)
    }

    interface ReadCallback {
        fun onStageStarted(stage: VerificationStage)
        fun onStageCompleted(stage: VerificationStage)
        fun onStageError(stage: VerificationStage, message: String)
        fun onCompleted(result: VerificationResult)
    }

    private val appContext = context.applicationContext
    private val main = Handler(Looper.getMainLooper())
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var readJob: Job? = null

    @Volatile
    var isReady: Boolean = false
        private set

    val sdkVersion: String
        get() = Tap2iDSdk.getSdkVersion()

    /** Validates the license key with Credence. Must succeed before [readWithNfc] / [readWithQr]. */
    fun init(apiKey: String, callback: InitCallback) {
        scope.launch {
            try {
                Tap2iDSdk.initSdk(SdkConfig(apiKey, appContext), object : InitSdkResultListener {
                    override fun onInitializationSuccess(result: SdkInitializationResult) {
                        val license = result.licenseVerificationResult
                        isReady = license.isValid
                        main.post {
                            if (license.isValid) callback.onReady(license)
                            else callback.onFailed("The Tap2iD license key is not valid for this app.")
                        }
                    }

                    override fun onInitializationFailure(error: Error) {
                        isReady = false
                        main.post { callback.onFailed(describe(error)) }
                    }
                })
            } catch (e: CancellationException) {
                throw e
            } catch (e: Throwable) {
                isReady = false
                main.post { callback.onFailed(describe(e)) }
            }
        }
    }

    /** NFC engagement: the provider taps their wallet phone on this phone. */
    fun readWithNfc(activity: Activity, callback: ReadCallback) =
        read(EngagementConfig(null, NfcConfig(activity)), callback)

    /** QR engagement: [mdocUri] is the "mdoc:..." text from the QR code the wallet shows. */
    fun readWithQr(mdocUri: String, callback: ReadCallback) =
        read(EngagementConfig(QrConfig(mdocUri), null), callback)

    /** Stops waiting for a result. Whether the SDK also tears down its NFC/BLE session on cancel is not documented. */
    fun cancel() {
        readJob?.cancel()
        readJob = null
    }

    private fun read(config: EngagementConfig, callback: ReadCallback) {
        cancel()
        readJob = scope.launch {
            try {
                Tap2iDSdk.verifyMdoc(config, object : MdocVerificationListener {
                    override fun onVerificationStageStarted(stage: VerificationStage) {
                        main.post { callback.onStageStarted(stage) }
                    }

                    override fun onVerificationStageCompleted(stage: VerificationStage) {
                        main.post { callback.onStageCompleted(stage) }
                    }

                    override fun onVerificationStageError(stage: VerificationStage, error: Throwable) {
                        main.post { callback.onStageError(stage, describe(error)) }
                    }

                    override fun onVerificationCompleted(result: VerificationResult) {
                        main.post { callback.onCompleted(result) }
                    }
                })
            } catch (e: CancellationException) {
                throw e
            } catch (e: Throwable) {
                main.post { callback.onStageError(VerificationStage.CONNECTION, describe(e)) }
            }
        }
    }

    private fun describe(t: Throwable): String = t.message?.takeIf { it.isNotBlank() } ?: t.javaClass.simpleName
}
