import 'dart:async';

import '../../network/api_error.dart';
import '../../platform/network/device_connectivity.dart';

const makoloServerUnavailableMessage =
    'Nos serveurs sont momentanément inaccessibles. '
    'Il s’agit probablement d’une panne temporaire. Réessayez dans un instant.';
const deviceOfflineMessage = 'Cet appareil est hors connexion.';

Future<bool> deviceIsOffline() => const DeviceConnectivity().isOffline();

bool _mayBeConnectivityFailure(Object error) =>
    error is TimeoutException || error is MakoloTransportError;

Future<String> resolvedAuthErrorMessage(
  Object error, {
  required String fallback,
}) async {
  if (_mayBeConnectivityFailure(error) && await deviceIsOffline()) {
    return deviceOfflineMessage;
  }
  return authErrorMessage(error, fallback: fallback);
}

String authErrorMessage(Object error, {required String fallback}) {
  if (error is TimeoutException || error is MakoloTransportError) {
    return makoloServerUnavailableMessage;
  }
  if (error is! MakoloApiError) return fallback;

  if (error.statusCode >= 500) return makoloServerUnavailableMessage;
  if (error.code == 'throttled' || error.statusCode == 429) {
    return 'Trop de tentatives pour le moment. Réessayez un peu plus tard.';
  }
  return fallback;
}

String signupErrorMessage(Object error) {
  if (error is! MakoloApiError) {
    return authErrorMessage(
      error,
      fallback: 'Création du compte impossible pour le moment. Réessayez dans un instant.',
    );
  }

  final fields = error.fields;
  if (fields.containsKey('email')) {
    final emailError = fields['email'].toString().toLowerCase();
    if (emailError.contains('already') ||
        emailError.contains('unique') ||
        emailError.contains('déjà')) {
      return 'Cette adresse e-mail est déjà associée à un compte. Connectez-vous ou utilisez « Mot de passe oublié ? ».';
    }
    return 'Vérifiez l’adresse e-mail indiquée.';
  }
  if (fields.containsKey('username')) {
    return 'Cet Identifiant Makolo ne peut pas être utilisé. Choisissez-en un autre.';
  }
  if (fields.containsKey('phone')) {
    return 'Vérifiez le numéro de téléphone indiqué.';
  }
  if (fields.containsKey('password') ||
      fields.containsKey('password_confirm')) {
    return 'Choisissez un mot de passe qui respecte les règles de sécurité et confirmez-le à l’identique.';
  }
  return authErrorMessage(
    error,
    fallback: 'Vérifiez les informations saisies puis réessayez.',
  );
}

String loginErrorMessage(Object error) {
  if (error is MakoloApiError &&
      (error.statusCode == 400 || error.statusCode == 401)) {
    return 'Identifiant Makolo, adresse e-mail ou mot de passe incorrect.';
  }
  return authErrorMessage(error, fallback: makoloServerUnavailableMessage);
}

Future<String> resolvedLoginErrorMessage(Object error) async {
  if (error is MakoloApiError &&
      (error.statusCode == 400 || error.statusCode == 401)) {
    return loginErrorMessage(error);
  }
  return resolvedAuthErrorMessage(
    error,
    fallback: makoloServerUnavailableMessage,
  );
}

Future<String> resolvedSignupErrorMessage(Object error) async {
  if (error is MakoloApiError) return signupErrorMessage(error);
  return resolvedAuthErrorMessage(
    error,
    fallback: 'Création du compte impossible pour le moment. Réessayez dans un instant.',
  );
}
