package com.makolo

import android.Manifest
import android.content.pm.PackageManager
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import java.util.Locale
import android.content.ContentValues
import android.content.Intent
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Environment
import android.provider.MediaStore
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.OpenableColumns
import android.util.Patterns
import io.flutter.embedding.android.FlutterFragmentActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.File

class MainActivity : FlutterFragmentActivity() {
    companion object {
        private const val SHARE_CHANNEL = "makolo/native_share"
        private const val DOWNLOAD_CHANNEL = "makolo/downloads"
        private const val DEVICE_CHANNEL = "makolo/device"
        private const val SPEECH_CHANNEL = "makolo/native_dictation"
        private const val ALERT_CHANNEL = "makolo_alerts"
    }

    private var shareChannel: MethodChannel? = null
    private var speechChannel: MethodChannel? = null
    private var speechRecognizer: SpeechRecognizer? = null
    private var pendingShare: Map<String, Any?>? = null
    private var launchReady = false
    private var removeNativeSplash: (() -> Unit)? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = getSystemService(NotificationManager::class.java)
            val channel = NotificationChannel(
                ALERT_CHANNEL, "Notifications Makolo", NotificationManager.IMPORTANCE_DEFAULT
            )
            channel.setShowBadge(false)
            manager.createNotificationChannel(channel)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            // Flutter may draw immediately. Keep this same native view only
            // while its real local initialization is unfinished, never for a timer.
            splashScreen.setOnExitAnimationListener { view ->
                if (launchReady) view.remove() else removeNativeSplash = { view.remove() }
            }
        }
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "makolo/launch")
            .setMethodCallHandler { call, result ->
                if (call.method == "ready") {
                    launchReady = true
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                        removeNativeSplash?.invoke()
                        removeNativeSplash = null
                    }
                    result.success(null)
                } else {
                    result.notImplemented()
                }
            }
        shareChannel = MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            SHARE_CHANNEL,
        ).also { channel ->
            channel.setMethodCallHandler { call, result ->
                when (call.method) {
                    "initialShare" -> {
                        // Consume each Android share intent once; remounting the
                        // Flutter router must not re-import a previous payload.
                        val payload = pendingShare
                        pendingShare = null
                        result.success(payload)
                    }
                    "copySharedUri" -> copySharedUri(call.arguments, result)
                    else -> result.notImplemented()
                }
            }
        }
        speechChannel = MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger, SPEECH_CHANNEL
        ).also { channel ->
            channel.setMethodCallHandler { call, result ->
                when (call.method) {
                    "available" -> result.success(
                        SpeechRecognizer.isRecognitionAvailable(this)
                    )
                    "start" -> startNativeDictation(result)
                    "stop" -> {
                        speechRecognizer?.stopListening()
                        result.success(null)
                    }
                    "cancel" -> {
                        releaseNativeDictation()
                        result.success(null)
                    }
                    else -> result.notImplemented()
                }
            }
        }
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, DEVICE_CHANNEL)
            .setMethodCallHandler { call, result ->
                if (call.method == "name") {
                    // Only the public manufacturer/model, never a hardware ID or user-assigned name.
                    val maker = Build.MANUFACTURER.orEmpty().trim()
                    val model = Build.MODEL.orEmpty().trim()
                    val name = if (model.startsWith(maker, ignoreCase = true)) model
                               else listOf(maker, model).filter { it.isNotBlank() }.joinToString(" ")
                    result.success(name.take(80))
                } else {
                    result.notImplemented()
                }
            }
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, DOWNLOAD_CHANNEL)
            .setMethodCallHandler { call, result ->
                if (call.method == "saveFile") {
                    saveToDownloads(call.arguments, result)
                } else {
                    result.notImplemented()
                }
            }
        if (pendingShare == null) {
            pendingShare = parseShareIntent(intent)
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        val payload = parseShareIntent(intent) ?: return
        val channel = shareChannel
        if (channel == null) {
            pendingShare = payload
        } else {
            channel.invokeMethod("shareReceived", payload)
        }
    }

    private fun speechEvent(type: String, value: String? = null) {
        val payload = mutableMapOf<String, Any>("type" to type)
        if (value != null) payload["text"] = value
        speechChannel?.invokeMethod("speechEvent", payload)
    }

    private fun releaseNativeDictation() {
        val active = speechRecognizer
        speechRecognizer = null
        try {
            active?.cancel()
            active?.destroy()
        } catch (_: Exception) {
            // The Android recognizer may have been released by the OS.
        }
    }

    private fun startNativeDictation(result: MethodChannel.Result) {
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            result.error("not_available", "No system speech recognition capability.", null)
            return
        }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            result.error("permission_denied", "Microphone permission required.", null)
            return
        }
        if (speechRecognizer != null) {
            result.error("already_listening", "Recognition is already running.", null)
            return
        }
        try {
            val recognizer = SpeechRecognizer.createSpeechRecognizer(this)
            speechRecognizer = recognizer
            recognizer.setRecognitionListener(object : RecognitionListener {
                override fun onReadyForSpeech(params: Bundle?) {
                    speechEvent("listening")
                }
                override fun onBeginningOfSpeech() {}
                override fun onRmsChanged(rmsdB: Float) {}
                override fun onBufferReceived(buffer: ByteArray?) {}
                override fun onEndOfSpeech() {
                    speechEvent("processing")
                }
                override fun onError(error: Int) {
                    if (speechRecognizer !== recognizer) return
                    speechEvent("error", error.toString())
                    releaseNativeDictation()
                }
                override fun onResults(results: Bundle?) {
                    if (speechRecognizer !== recognizer) return
                    val words = results?.getStringArrayList(
                        SpeechRecognizer.RESULTS_RECOGNITION
                    )?.firstOrNull().orEmpty()
                    speechEvent(if (words.isBlank()) "empty" else "final", words)
                    releaseNativeDictation()
                }
                override fun onPartialResults(partialResults: Bundle?) {
                    val words = partialResults?.getStringArrayList(
                        SpeechRecognizer.RESULTS_RECOGNITION
                    )?.firstOrNull()
                    if (!words.isNullOrBlank()) speechEvent("partial", words)
                }
                override fun onEvent(eventType: Int, params: Bundle?) {}
            })
            val speechIntent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(
                    RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                    RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
                )
                putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault().toLanguageTag())
            }
            recognizer.startListening(speechIntent)
            result.success(null)
        } catch (_: Exception) {
            releaseNativeDictation()
            result.error("start_failed", "System speech recognition could not start.", null)
        }
    }

    override fun onDestroy() {
        releaseNativeDictation()
        speechChannel?.setMethodCallHandler(null)
        speechChannel = null
        super.onDestroy()
    }

    private fun parseShareIntent(intent: Intent?): Map<String, Any?>? {
        if (intent == null) return null
        val action = intent.action
        if (action != Intent.ACTION_SEND && action != Intent.ACTION_SEND_MULTIPLE) {
            return null
        }

        val uris = sharedUris(intent)
        if (uris.isNotEmpty()) {
            return mapOf(
                "kind" to "files",
                "files" to uris.map { uri ->
                    mapOf(
                        "uri" to uri.toString(),
                        "name" to displayName(uri),
                        "mime_type" to contentResolver.getType(uri),
                    )
                },
            )
        }

        val text = intent.getStringExtra(Intent.EXTRA_TEXT)?.trim()
        if (text.isNullOrEmpty()) return null
        val isUrl = Patterns.WEB_URL.matcher(text).matches()
        return mapOf(
            "kind" to if (isUrl) "url" else "text",
            "text" to text,
        )
    }

    @Suppress("DEPRECATION")
    private fun sharedUris(intent: Intent): List<Uri> {
        return when (intent.action) {
            Intent.ACTION_SEND -> {
                val uri = intent.getParcelableExtra<Uri>(Intent.EXTRA_STREAM)
                if (uri == null) emptyList() else listOf(uri)
            }
            Intent.ACTION_SEND_MULTIPLE ->
                intent.getParcelableArrayListExtra<Uri>(Intent.EXTRA_STREAM)
                    ?: emptyList()
            else -> emptyList()
        }
    }

    private fun displayName(uri: Uri): String {
        if (uri.scheme == "content") {
            contentResolver.query(
                uri,
                arrayOf(OpenableColumns.DISPLAY_NAME),
                null,
                null,
                null,
            )?.use { cursor ->
                if (cursor.moveToFirst()) {
                    val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                    if (index >= 0) {
                        val value = cursor.getString(index)
                        if (!value.isNullOrBlank()) return value
                    }
                }
            }
        }
        return uri.lastPathSegment?.substringAfterLast('/') ?: "shared-file"
    }

    private fun copySharedUri(arguments: Any?, result: MethodChannel.Result) {
        val map = arguments as? Map<*, *>
        val rawUri = map?.get("uri")?.toString()
        val destinationPath = map?.get("destination_path")?.toString()
        if (rawUri.isNullOrBlank() || destinationPath.isNullOrBlank()) {
            result.error("invalid_arguments", "Missing share copy arguments.", null)
            return
        }

        val uri = Uri.parse(rawUri)
        if (uri.scheme != "content") {
            result.error("unsupported_uri", "Only content URIs are accepted.", null)
            return
        }

        try {
            val destination = File(destinationPath)
            destination.parentFile?.mkdirs()
            val input = contentResolver.openInputStream(uri)
                ?: throw IllegalStateException("Shared content is unavailable.")
            input.use { source ->
                destination.outputStream().use { target ->
                    source.copyTo(target)
                }
            }
            result.success(null)
        } catch (error: Exception) {
            result.error("share_copy_failed", "Unable to stage shared content.", null)
        }
    }
    private fun saveToDownloads(arguments: Any?, result: MethodChannel.Result) {
        val args = arguments as? Map<*, *>
        val path = args?.get("source_path") as? String
        val name = args?.get("file_name") as? String
        val mime = args?.get("mime_type") as? String
        if (path.isNullOrBlank() || name.isNullOrBlank() || mime.isNullOrBlank()) {
            result.error("invalid_arguments", "Missing download parameters.", null)
            return
        }
        // Never use remote URLs or filesystem paths as exported filenames.
        if (name != File(name).name || name == "." || name == ".." ||
            name.contains('/') || name.contains('\\') || name.any { it.code < 32 }) {
            result.error("invalid_filename", "Unsafe download filename.", null)
            return
        }
        val source = File(path)
        if (!source.isFile || source.length() <= 0L) {
            result.error("missing_file", "The download is unavailable.", null)
            return
        }
        // Scoped storage owns public Downloads on Android 10+. On older
        // Android versions no share-picker or silent private-cache fallback.
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            result.error("unsupported_android", "Downloads requires Android 10 or later.", null)
            return
        }
        val values = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, name)
            put(MediaStore.MediaColumns.MIME_TYPE, mime)
            put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
            put(MediaStore.MediaColumns.IS_PENDING, 1)
        }
        var destination: Uri? = null
        try {
            destination = contentResolver.insert(
                MediaStore.Downloads.EXTERNAL_CONTENT_URI, values,
            ) ?: throw IllegalStateException("Cannot create download.")
            contentResolver.openOutputStream(destination)?.use { output ->
                source.inputStream().use { input -> input.copyTo(output) }
            } ?: throw IllegalStateException("Cannot write download.")
            val publish = ContentValues().apply {
                put(MediaStore.MediaColumns.IS_PENDING, 0)
            }
            contentResolver.update(destination, publish, null, null)
            result.success(name)
        } catch (error: Exception) {
            destination?.let { contentResolver.delete(it, null, null) }
            result.error("download_failed", "Unable to save to Downloads.", null)
        }
    }


}
