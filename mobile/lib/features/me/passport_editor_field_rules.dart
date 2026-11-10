/// Local checks for the Accounts-backed Passport editor.
///
/// The server remains authoritative for uniqueness, permissions and storage.
class PassportEditorFieldRules {
  const PassportEditorFieldRules._();

  static const Map<String, int> maxLengths = {
    'first_name': 150,
    'last_name': 150,
    'phone': 30,
    'profession': 255,
    'company_name': 255,
    'organization_name': 255,
    'city': 100,
    'country': 100,
    'website': 200,
    'linkedin_url': 200,
    'facebook_url': 200,
    'instagram_url': 200,
    'tiktok_url': 200,
    'x_url': 200,
    'youtube_url': 200,
  };

  static const Set<String> linkFields = {
    'website',
    'linkedin_url',
    'facebook_url',
    'instagram_url',
    'tiktok_url',
    'x_url',
    'youtube_url',
  };

  static const Map<String, List<String>> socialHosts = {
    'linkedin_url': ['linkedin.com'],
    'facebook_url': ['facebook.com', 'fb.com'],
    'instagram_url': ['instagram.com'],
    'tiktok_url': ['tiktok.com'],
    'x_url': ['x.com', 'twitter.com'],
    'youtube_url': ['youtube.com', 'youtu.be'],
  };

  // Mirrors Accounts' reserved slugs for immediate feedback.
  // Server-side Accounts validation is the final authority.
  static const Set<String> reservedIdentifiers = {
    'admin',
    'api',
    'help',
    'login',
    'logout',
    'makolo',
    'me',
    'support',
    'system',
    'account',
    'activities',
    'analytics',
    'auth',
    'autopilot',
    'conversations',
    'crm',
    'dashboard',
    'discover',
    'events',
    'funding',
    'g',
    'goals',
    'groups',
    'growth',
    'journeys',
    'library',
    'mark',
    'network',
    'notifications',
    'o',
    'objectives',
    'obtention',
    'operations',
    'opportunities',
    'partners',
    'passport',
    'payments',
    'preparation',
    'promotions',
    'questionnaires',
    'recognition',
    'scanner',
    'services',
    'shares',
    'sharing',
    'spaces',
    'subscription',
    'tickets',
    'transport',
    'trust',
  };

  static bool isLink(String key) => linkFields.contains(key);

  /// Idempotent, including if the user pasted a duplicated scheme.
  static String normalize(String key, String raw) {
    final input = raw.trim();
    if (input.isEmpty) return '';
    if (key == 'username') {
      return input.replaceFirst(RegExp(r'^@+'), '').toLowerCase();
    }
    if (isLink(key)) {
      final withoutScheme = input.replaceFirst(
        RegExp(r'^(?:(?:https?):\/\/)+', caseSensitive: false),
        '',
      );
      // A half-entered host is not yet something we can confidently fix.
      if (!withoutScheme.contains('.') ||
          RegExp(r'\s').hasMatch(withoutScheme)) {
        return input;
      }
      return Uri(scheme: 'https').toString() + '//' + withoutScheme;
    }
    if (key == 'bio' || key == 'address') return input;
    return input.replaceAll(RegExp(r'[ \t]+'), ' ');
  }

  /// Short inline feedback. Optional empty values never show an error.
  static String? error(String key, String raw) {
    final value = normalize(key, raw);
    if (value.isEmpty) return null;

    if (key == 'username') {
      if (value.runes.length < 3 || value.runes.length > 30) {
        return '3 à 30 caractères.';
      }
      if (!RegExp(r'^[a-z0-9](?:[a-z0-9._-]{1,28}[a-z0-9])?$')
          .hasMatch(value)) {
        return 'Identifiant invalide.';
      }
      if (reservedIdentifiers.contains(value)) return 'Identifiant réservé.';
      return null;
    }

    final max = maxLengths[key];
    if (max != null && value.runes.length > max) {
      return '$max caractères maximum.';
    }

    if (key == 'phone') {
      if (!RegExp(r'^(?:\+?[0-9][0-9() .-]*|\(\+[0-9]{1,4}\)[0-9() .-]*)$')
          .hasMatch(value)) {
        return 'Numéro invalide.';
      }
      final digits = RegExp(r'[0-9]').allMatches(value).length;
      if (digits < 7 || digits > 15) return '7 à 15 chiffres.';
    }

    if (isLink(key)) {
      if (RegExp(r'\s').hasMatch(value)) return 'Lien invalide.';
      final uri = Uri.tryParse(value);
      if (uri == null ||
          uri.scheme != 'https' ||
          uri.host.isEmpty ||
          uri.userInfo.isNotEmpty) {
        return 'Lien invalide.';
      }
      final host = uri.host.toLowerCase();
      if (!RegExp(r'^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9-]{2,63}$')
          .hasMatch(host)) {
        return 'Lien invalide.';
      }
      final requiredHosts = socialHosts[key];
      if (requiredHosts != null &&
          !requiredHosts.any(
            (domain) => host == domain || host.endsWith('.$domain'),
          )) {
        return 'Lien invalide.';
      }
    }

    if (key == 'birth_date') {
      if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(value)) {
        return 'Date invalide.';
      }
      final parsed = DateTime.tryParse(value);
      if (parsed == null ||
          '${parsed.year.toString().padLeft(4, '0')}-${parsed.month.toString().padLeft(2, '0')}-${parsed.day.toString().padLeft(2, '0')}' !=
              value ||
          parsed.isAfter(DateTime.now())) {
        return 'Date invalide.';
      }
    }
    return null;
  }
}
