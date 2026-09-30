package com.makolo

import android.content.Intent
import android.net.Uri
import android.provider.OpenableColumns
import android.util.Patterns
import io.flutter.embedding.android.FlutterFragmentActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.File

class MainActivity : FlutterFragmentActivity() {
    companion object {
        private const val SHARE_CHANNEL = "makolo/native_share"
    }

    private var shareChannel: MethodChannel? = null
    private var pendingShare: Map<String, Any?>? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        shareChannel = MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            SHARE_CHANNEL,
        ).also { channel ->
            channel.setMethodCallHandler { call, result ->
                when (call.method) {
                    "initialShare" -> {
                        val payload = pendingShare ?: parseShareIntent(intent)
                        pendingShare = null
                        result.success(payload)
                    }
                    "copySharedUri" -> copySharedUri(call.arguments, result)
                    else -> result.notImplemented()
                }
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
}
