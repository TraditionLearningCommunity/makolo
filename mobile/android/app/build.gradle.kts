import java.io.FileInputStream
import java.util.Properties

plugins {
    id("com.android.application")
    id("dev.flutter.flutter-gradle-plugin")
    id("com.google.gms.google-services")
}

val makoloSigningProperties = Properties()
val makoloSigningPropertiesFile = rootProject.file("key.properties")
if (makoloSigningPropertiesFile.exists()) {
    FileInputStream(makoloSigningPropertiesFile).use(makoloSigningProperties::load)
}

fun makoloSigningValue(property: String, environment: String): String? {
    return makoloSigningProperties.getProperty(property)?.trim()?.takeIf { it.isNotEmpty() }
        ?: System.getenv(environment)?.trim()?.takeIf { it.isNotEmpty() }
}

val makoloReleaseStoreFile = makoloSigningValue("storeFile", "MAKOLO_ANDROID_KEYSTORE_PATH")
val makoloReleaseStorePassword = makoloSigningValue("storePassword", "MAKOLO_ANDROID_KEYSTORE_PASSWORD")
val makoloReleaseKeyAlias = makoloSigningValue("keyAlias", "MAKOLO_ANDROID_KEY_ALIAS")
val makoloReleaseKeyPassword = makoloSigningValue("keyPassword", "MAKOLO_ANDROID_KEY_PASSWORD")
val makoloReleaseSigningConfigured = listOf(
    makoloReleaseStoreFile,
    makoloReleaseStorePassword,
    makoloReleaseKeyAlias,
    makoloReleaseKeyPassword,
).all { !it.isNullOrBlank() }

val makoloAppLinkScheme = System.getenv("MAKOLO_ANDROID_APP_LINK_SCHEME")
    ?.trim()
    ?.takeIf { it.isNotEmpty() }
val makoloAppLinkHost = System.getenv("MAKOLO_ANDROID_APP_LINK_HOST")
    ?.trim()
    ?.takeIf { it.isNotEmpty() }
val makoloAppLinksConfigured =
    makoloAppLinkScheme in setOf("https") &&
    !makoloAppLinkHost.isNullOrBlank() &&
    !makoloAppLinkHost!!.contains("/") &&
    !makoloAppLinkHost.contains("://")

android {
    namespace = "com.makolo"
    compileSdk = 37
    ndkVersion = flutter.ndkVersion

    compileOptions {
        isCoreLibraryDesugaringEnabled = true
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    signingConfigs {
        if (makoloReleaseSigningConfigured) {
            create("release") {
                storeFile = rootProject.file(makoloReleaseStoreFile!!)
                storePassword = makoloReleaseStorePassword
                keyAlias = makoloReleaseKeyAlias
                keyPassword = makoloReleaseKeyPassword
            }
        }
    }

    defaultConfig {
        applicationId = "com.makolo"
        minSdk = maxOf(flutter.minSdkVersion, 24)
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    flavorDimensions += "environment"
    productFlavors {
        create("dev") {
            dimension = "environment"
            applicationId = "com.makolo.dev"
            // DEV may stay locally installable without production signing material.
            signingConfig = signingConfigs.getByName("debug")
        }
        create("beta") {
            dimension = "environment"
            applicationId = "com.makolo.beta"
            manifestPlaceholders["makoloAppLinkScheme"] = makoloAppLinkScheme ?: "https"
            manifestPlaceholders["makoloAppLinkHost"] =
                makoloAppLinkHost ?: "app-links-not-configured.invalid"
        }
        create("prod") {
            dimension = "environment"
            applicationId = "com.makolo"
            manifestPlaceholders["makoloAppLinkScheme"] = makoloAppLinkScheme ?: "https"
            manifestPlaceholders["makoloAppLinkHost"] =
                makoloAppLinkHost ?: "app-links-not-configured.invalid"
        }
    }

    buildTypes {
        release {
            if (makoloReleaseSigningConfigured) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

dependencies {
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")
}

val makoloSignedReleaseTasks = setOf(
    "assembleBetaRelease",
    "bundleBetaRelease",
    "assembleProdRelease",
    "bundleProdRelease",
)

tasks.configureEach {
    if (name in makoloSignedReleaseTasks) {
        doFirst {
            check(makoloReleaseSigningConfigured) {
                "Makolo beta/prod release signing is not configured. " +
                    "Provide android/key.properties or the MAKOLO_ANDROID_KEYSTORE_* environment variables."
            }
            check(makoloAppLinksConfigured) {
                "Makolo beta/prod App Links are not configured. " +
                    "Provide MAKOLO_ANDROID_APP_LINK_SCHEME=https and MAKOLO_ANDROID_APP_LINK_HOST."
            }
        }
    }

    if (name.contains("GoogleServices", ignoreCase = true)) {
        val variant = name.removePrefix("process").removeSuffix("GoogleServices").lowercase()
        val flavor = listOf("dev", "beta", "prod").firstOrNull { variant.startsWith(it) }
        val config = flavor?.let { file("src/$it/google-services.json") }
        onlyIf { config?.exists() == true }
    }
}

flutter {
    source = "../.."
}
