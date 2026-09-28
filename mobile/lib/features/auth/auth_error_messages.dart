import '../../network/api_error.dart';

String authErrorMessage(Object error, {required String fallback}) {
  if (error is! MakoloApiError) return fallback;

  if (error.code == 'throttled' || error.statusCode == 429) {
    return 'Trop de tentatives pour le moment. Réessayez un peu plus tard.';
  }
  if (error.statusCode >= 500) {
    return fallback;
  }
  return fallback;
}

String signupErrorMessage(Object error) {
  if (error is! MakoloApiError) {
    return 'Création du compte impossible pour le moment. Réessayez dans un instant.';
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
