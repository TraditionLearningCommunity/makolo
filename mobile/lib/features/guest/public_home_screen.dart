import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../design/makolo_theme.dart';
import 'public_shell.dart';

/// A calm public threshold, not a second Discovery engine or a marketing feed.
class PublicHomeScreen extends StatefulWidget {
  const PublicHomeScreen({super.key});

  @override
  State<PublicHomeScreen> createState() => _PublicHomeScreenState();
}

class _PublicHomeScreenState extends State<PublicHomeScreen> {
  final _search = TextEditingController();

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  void _explore([String? vertical]) {
    final query = <String, String>{
      if (_search.text.trim().isNotEmpty) 'q': _search.text.trim(),
      if (vertical != null) 'vertical': vertical,
    };
    final suffix = Uri(queryParameters: query).query;
    context.go(suffix.isEmpty ? '/discover' : '/discover?$suffix');
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return PublicExperienceShell(
      current: 0,
      child: ListView(
        key: const Key('guest-public-home'),
        padding: const EdgeInsets.all(MakoloSpacing.lg),
        children: [
          const SizedBox(height: MakoloSpacing.lg),
          Text('MAKOLO', style: theme.textTheme.labelMedium?.copyWith(
            color: theme.colorScheme.primary,
          )),
          const SizedBox(height: MakoloSpacing.sm),
          Text(
            'Faites avancer ce qui compte.',
            style: theme.textTheme.headlineMedium,
          ),
          const SizedBox(height: MakoloSpacing.sm),
          const Text('Trouvez ce que vous voulez vivre, faire ou obtenir.'),
          const SizedBox(height: MakoloSpacing.xl),
          TextField(
            key: const Key('guest-home-query'),
            controller: _search,
            textInputAction: TextInputAction.search,
            onSubmitted: (_) => _explore(),
            decoration: const InputDecoration(
              labelText: 'Que souhaitez-vous faire ?',
              hintText: 'Ex. Voyager à Kolwezi demain matin',
              prefixIcon: Icon(Icons.search),
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: MakoloSpacing.sm),
          FilledButton.icon(
            onPressed: () => _explore(),
            icon: const Icon(Icons.arrow_forward),
            label: const Text('Découvrir'),
          ),
          const SizedBox(height: MakoloSpacing.xl),
          Text('Explorer autrement', style: theme.textTheme.titleLarge),
          const SizedBox(height: MakoloSpacing.md),
          Wrap(
            spacing: MakoloSpacing.sm,
            runSpacing: MakoloSpacing.sm,
            children: [
              ActionChip(
                avatar: const Icon(Icons.directions_bus_outlined),
                label: const Text('Voyager'),
                onPressed: () => _explore('transport'),
              ),
              ActionChip(
                avatar: const Icon(Icons.event_outlined),
                label: const Text('Événements'),
                onPressed: () => _explore('event'),
              ),
              ActionChip(
                avatar: const Icon(Icons.handshake_outlined),
                label: const Text('Être accompagné'),
                onPressed: () => _explore('service'),
              ),
              ActionChip(
                avatar: const Icon(Icons.explore_outlined),
                label: const Text('Toutes les possibilités'),
                onPressed: () => _explore(),
              ),
            ],
          ),
          const SizedBox(height: MakoloSpacing.xl),
          Card(
            child: ListTile(
              leading: const Icon(Icons.groups_outlined),
              title: const Text('Les Espaces sur Makolo'),
              subtitle: const Text(
                'Découvrez les organisations, équipes et communautés qui rendent des possibilités accessibles.',
              ),
              isThreeLine: true,
              trailing: const Icon(Icons.arrow_forward_ios, size: 16),
              onTap: () => context.go('/spaces'),
            ),
          ),
        ],
      ),
    );
  }
}
