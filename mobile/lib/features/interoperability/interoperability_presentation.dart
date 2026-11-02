import '../../repositories/interoperability_repository.dart';

/// One Flutter presentation vocabulary for Profile and Space, mirroring
/// interoperability.presentation (Web). These labels never grant authority.
String connectionStatusLabel(InteroperabilityConnectionProjection row) {
  if (!row.enabled || row.status == 'disabled') return 'Désactivé';
  if (row.health == 'unavailable') return 'Momentanément indisponible';
  if (row.health == 'degraded') {
    return row.connected
        ? 'Connecté · disponibilité réduite'
        : 'Disponibilité réduite';
  }
  if (row.health == 'unknown') {
    return row.connected ? 'Connecté · état à vérifier' : 'État à vérifier';
  }
  if (row.connected && row.usable) return 'Connecté et disponible';
  if (row.connected && row.capabilities.isEmpty) {
    return 'Relié · aucune capacité active';
  }
  if (row.connected) return 'Connecté';
  return row.available ? 'Disponible' : 'État à vérifier';
}

String connectionExperienceMessage(InteroperabilityConnectionProjection row) {
  if (!row.enabled || row.status == 'disabled') {
    return 'Cette connexion est désactivée.';
  }
  if (row.health == 'unavailable') {
    return 'Le service ne répond pas actuellement.';
  }
  if (row.health == 'degraded') {
    return 'Le service peut être temporairement limité.';
  }
  if (row.health == 'unknown') {
    return 'La disponibilité doit être vérifiée.';
  }
  if (row.connected && row.capabilities.isEmpty) {
    return 'Aucune capacité active n’est exposée.';
  }
  if (row.usable) return 'Cette connexion possède une capacité active.';
  return 'Aucune action n’est disponible depuis cette connexion.';
}

String connectionCapabilityLabel(String value) => switch (value) {
  'text_generate' => 'Génération de texte',
  'structured_generate' => 'Données structurées',
  'embed' => 'Représentation sémantique',
  'rerank' => 'Classement de résultats',
  'web_research' => 'Recherche sur le Web',
  _ => _humanize(value, 'Capacité disponible'),
};

String _humanize(String value, String fallback) {
  final text = value
      .trim()
      .replaceAll(RegExp(r'[._-]'), ' ')
      .replaceAll(RegExp(r'\s+'), ' ')
      .trim();
  if (text.isEmpty) return fallback;
  return text[0].toUpperCase() + text.substring(1);
}
