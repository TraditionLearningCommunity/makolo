import 'package:flutter/material.dart';

import '../../design/makolo_theme.dart';

/// N3 presents only authority freshly acquired from the server.
class SpaceUsAuthorityFacts extends StatelessWidget {
  const SpaceUsAuthorityFacts({super.key, required this.payload});

  final Map<String, dynamic> payload;

  @override
  Widget build(BuildContext context) {
    final rows = payload['mandates'];
    if (rows is! List) {
      return const Text('Autorisations indisponibles.');
    }
    if (rows.isEmpty) {
      return const Text('Aucune autorisation active.');
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final row in rows)
          if (row is Map)
            Padding(
              padding: const EdgeInsets.only(bottom: MakoloSpacing.md),
              child: _AuthorityCard(data: _map(row)),
            ),
      ],
    );
  }
}

class _AuthorityCard extends StatelessWidget {
  const _AuthorityCard({required this.data});

  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    final role = _map(data['role']);
    final scope = _map(data['scope']);
    final permissions = data['permissions'];
    final validFrom = _date(context, data['valid_from']);
    final validUntil = _date(context, data['valid_until']);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(MakoloSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              _label(role['label'], 'Responsabilité'),
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: MakoloSpacing.xs),
            Text(
              '${_label(scope['label'], 'Portée')} · '
              '${_label(scope['target'], 'Non précisée')}',
            ),
            if (_label(role['description'], '').isNotEmpty) ...[
              const SizedBox(height: MakoloSpacing.xs),
              Text(_label(role['description'], '')),
            ],
            const SizedBox(height: MakoloSpacing.sm),
            if (validFrom != null) Text('Valable depuis le $validFrom'),
            Text(
              validUntil == null
                  ? 'Aucune date de fin définie'
                  : 'Fin de validité : $validUntil',
            ),
            const SizedBox(height: MakoloSpacing.md),
            Text(
              'Droits associés à ce rôle',
              style: Theme.of(context).textTheme.titleSmall,
            ),
            if (permissions is! List || permissions.isEmpty)
              const Text('Aucun droit actif associé à ce rôle.')
            else
              for (final entry in permissions)
                if (entry is Map)
                  Padding(
                    padding: const EdgeInsets.only(top: MakoloSpacing.xs),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.check_circle_outline, size: 18),
                        const SizedBox(width: MakoloSpacing.sm),
                        Expanded(
                          child: Text(_label(_map(entry)['label'], 'Droit')),
                        ),
                      ],
                    ),
                  ),
          ],
        ),
      ),
    );
  }

  String? _date(BuildContext context, Object? value) {
    if (value is! String || value.isEmpty) return null;
    final parsed = DateTime.tryParse(value);
    if (parsed == null) return null;
    final local = parsed.toLocal();
    final labels = MaterialLocalizations.of(context);
    return '${labels.formatMediumDate(local)} · '
        '${labels.formatTimeOfDay(TimeOfDay.fromDateTime(local))}';
  }
}

Map<String, dynamic> _map(Object? raw) => raw is Map
    ? raw.map((key, value) => MapEntry(key.toString(), value))
    : <String, dynamic>{};

String _label(Object? value, String fallback) =>
    value is String && value.trim().isNotEmpty ? value.trim() : fallback;
