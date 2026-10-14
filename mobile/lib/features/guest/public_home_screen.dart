import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../design/makolo_theme.dart';
import 'public_shell.dart';

/// Public entry point: orientation towards Discover, not a second feed.
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

  void _explore({String? vertical, bool includeQuery = true}) {
    FocusManager.instance.primaryFocus?.unfocus();
    final query = <String, String>{
      if (includeQuery && _search.text.trim().isNotEmpty)
        'q': _search.text.trim(),
      if (vertical != null) 'vertical': vertical,
    };
    final suffix = Uri(queryParameters: query).query;
    context.go(suffix.isEmpty ? '/discover' : '/discover?$suffix');
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;
    final muted = colors.onSurfaceVariant;
    final border = colors.outlineVariant;

    return PublicExperienceShell(
      current: 0,
      child: ListView(
        key: const Key('guest-public-home'),
        padding: const EdgeInsets.all(MakoloSpacing.lg),
        children: [
          const SizedBox(height: MakoloSpacing.sm),
          Text(
            'DÉCOUVRIR · PRÉPARER · AVANCER',
            style: theme.textTheme.labelSmall?.copyWith(
              color: colors.primary,
              fontWeight: FontWeight.w800,
              letterSpacing: 1,
            ),
          ),
          const SizedBox(height: MakoloSpacing.md),
          Text(
            'Ce que vous voulez faire commence ici.',
            style: theme.textTheme.headlineMedium?.copyWith(
              fontWeight: FontWeight.w800,
              height: 1.13,
            ),
          ),
          const SizedBox(height: MakoloSpacing.md),
          Text(
            'Trouvez des activités, des services, des occasions et des '
            'personnes ou organisations qui peuvent vous aider à avancer.',
            style: theme.textTheme.bodyLarge?.copyWith(
              color: muted,
              height: 1.5,
            ),
          ),
          const SizedBox(height: MakoloSpacing.xl),
          Text(
            'Rechercher des possibilités',
            style: theme.textTheme.titleSmall?.copyWith(
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: MakoloSpacing.sm),
          Semantics(
            label: 'Rechercher des possibilités',
            child: TextField(
              key: const Key('guest-home-query'),
              controller: _search,
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => _explore(),
              onTapOutside: (_) =>
                  FocusManager.instance.primaryFocus?.unfocus(),
              decoration: InputDecoration(
                hintText: 'Voyager, participer, être accompagné…',
                hintMaxLines: 2,
                prefixIcon: const Icon(Icons.search_rounded),
                suffixIcon: IconButton(
                  key: const Key('guest-home-search-submit'),
                  tooltip: 'Lancer la recherche',
                  onPressed: _explore,
                  icon: const Icon(Icons.arrow_forward_rounded),
                ),
                filled: true,
                fillColor: colors.surface,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(MakoloRadii.card),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(MakoloRadii.card),
                  borderSide: BorderSide(color: border),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(MakoloRadii.card),
                  borderSide: BorderSide(color: colors.primary, width: 2),
                ),
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: MakoloSpacing.md,
                  vertical: MakoloSpacing.md,
                ),
              ),
            ),
          ),
          const SizedBox(height: MakoloSpacing.md),
          Wrap(
            spacing: MakoloSpacing.sm,
            runSpacing: MakoloSpacing.sm,
            children: [
              _ExploreChip(
                label: 'Voyager',
                icon: Icons.directions_bus_outlined,
                onPressed: () =>
                    _explore(vertical: 'transport', includeQuery: false),
              ),
              _ExploreChip(
                label: 'Participer',
                icon: Icons.event_outlined,
                onPressed: () =>
                    _explore(vertical: 'event', includeQuery: false),
              ),
              _ExploreChip(
                label: 'Être accompagné',
                icon: Icons.handshake_outlined,
                onPressed: () =>
                    _explore(vertical: 'service', includeQuery: false),
              ),
              _ExploreChip(
                label: 'Tout explorer',
                icon: Icons.explore_outlined,
                onPressed: () => _explore(includeQuery: false),
              ),
            ],
          ),
          const SizedBox(height: MakoloSpacing.strong),
          Container(
            padding: const EdgeInsets.all(MakoloSpacing.inner),
            decoration: BoxDecoration(
              color: colors.surface,
              borderRadius: BorderRadius.circular(MakoloRadii.large),
              border: Border.all(color: border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Makolo vous accompagne jusqu’à l’action',
                  style: theme.textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: MakoloSpacing.lg),
                const Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: _JourneyStep(
                        number: '01',
                        label: 'Découvrez',
                        icon: Icons.explore_outlined,
                      ),
                    ),
                    SizedBox(width: MakoloSpacing.sm),
                    Expanded(
                      child: _JourneyStep(
                        number: '02',
                        label: 'Préparez',
                        icon: Icons.fact_check_outlined,
                      ),
                    ),
                    SizedBox(width: MakoloSpacing.sm),
                    Expanded(
                      child: _JourneyStep(
                        number: '03',
                        label: 'Avancez',
                        icon: Icons.arrow_outward_rounded,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: MakoloSpacing.lg),
          Material(
            color: colors.surface,
            borderRadius: BorderRadius.circular(MakoloRadii.large),
            child: InkWell(
              key: const Key('guest-home-spaces'),
              borderRadius: BorderRadius.circular(MakoloRadii.large),
              onTap: () => context.go('/spaces'),
              child: Container(
                padding: const EdgeInsets.all(MakoloSpacing.inner),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(MakoloRadii.large),
                  border: Border.all(color: border),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      Icons.groups_outlined,
                      color: colors.primary,
                      size: 28,
                    ),
                    const SizedBox(width: MakoloSpacing.md),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Les Espaces sur Makolo',
                            style: theme.textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          const SizedBox(height: MakoloSpacing.xs),
                          Text(
                            'Découvrez les organisations, équipes et '
                            'communautés présentes sur Makolo.',
                            style: theme.textTheme.bodyMedium?.copyWith(
                              color: muted,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: MakoloSpacing.sm),
                    Icon(Icons.chevron_right_rounded, color: muted),
                  ],
                ),
              ),
            ),
          ),
          const SizedBox(height: MakoloSpacing.lg),
        ],
      ),
    );
  }
}

class _ExploreChip extends StatelessWidget {
  const _ExploreChip({
    required this.label,
    required this.icon,
    required this.onPressed,
  });

  final String label;
  final IconData icon;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return ActionChip(
      backgroundColor: colors.surface,
      side: BorderSide(color: colors.outlineVariant),
      shape: const StadiumBorder(),
      avatar: Icon(icon, size: 20, color: colors.primary),
      label: Text(label),
      onPressed: onPressed,
    );
  }
}

class _JourneyStep extends StatelessWidget {
  const _JourneyStep({
    required this.number,
    required this.label,
    required this.icon,
  });

  final String number;
  final String label;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 26, color: colors.primary),
        const SizedBox(height: MakoloSpacing.compact),
        Text(
          number,
          style: theme.textTheme.labelMedium?.copyWith(
            color: colors.primary,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: MakoloSpacing.xs),
        Text(
          label,
          style: theme.textTheme.bodyMedium?.copyWith(
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    );
  }
}
