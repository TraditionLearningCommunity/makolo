import 'package:flutter/material.dart';

/// A shared presentation cue, not an authority selector.
///
/// The owner and actor context are projected by Objectives on the server.
class ObjectiveContextBanner extends StatelessWidget {
  const ObjectiveContextBanner({super.key, required this.payload});

  final Map<String, dynamic> payload;

  static Map<String, dynamic> _object(Object? raw) =>
      raw is Map ? raw.map((key, value) => MapEntry('$key', value)) : {};

  @override
  Widget build(BuildContext context) {
    final owner = _object(payload['owner']);
    final lens = _object(payload['actor_context']);
    final inSpace = lens['kind'] == 'space';
    final name = (owner['label']?.toString() ?? '').trim();
    final title = inSpace
        ? 'Espace actif : \${name.isEmpty ? 'Espace' : name}'
        : 'Consultation depuis mon Profil';
    final detail = name.isEmpty
        ? 'Actions et informations selon les permissions serveur.'
        : 'Porteur : $name · Actions selon vos permissions.';
    final scheme = Theme.of(context).colorScheme;
    return Semantics(
      container: true,
      label: '$title. $detail',
      child: Card(
        elevation: 0,
        color: scheme.primaryContainer.withValues(alpha: .35),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 10),
          child: Row(
            children: [
              Icon(
                inSpace ? Icons.groups_outlined : Icons.person_outline_rounded,
                color: scheme.primary,
                size: 20,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      detail,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
