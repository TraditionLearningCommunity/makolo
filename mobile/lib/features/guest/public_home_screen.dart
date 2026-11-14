import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../design/makolo_theme.dart';
import 'public_shell.dart';

/// Guest orientation into Discover, not a second discovery feed.
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
      'vertical': ?vertical,
    };
    final suffix = Uri(queryParameters: query).query;
    context.go(suffix.isEmpty ? '/discover' : '/discover?$suffix');
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;
    final muted = colors.onSurfaceVariant;
    final edge = MediaQuery.sizeOf(context).width <= 360
        ? MakoloSpacing.md
        : MakoloSpacing.inner;

    return PublicExperienceShell(
      current: 0,
      child: ListView(
        key: const Key('guest-public-home'),
        padding: EdgeInsets.fromLTRB(
          edge,
          MakoloSpacing.inner,
          edge,
          MediaQuery.sizeOf(context).height < 700
              ? MakoloSpacing.exceptional
              : MakoloSpacing.lg,
        ),
        children: [
          Text(
            'Ça vous intéresserait',
            style: theme.textTheme.headlineMedium?.copyWith(
              fontWeight: FontWeight.w800,
              letterSpacing: -0.6,
              height: 1.12,
            ),
          ),
          const SizedBox(height: MakoloSpacing.sm),
          Text(
            'Découvrez des activités, des services, des événements et des '
            'opportunités pour avancer dans ce qui compte pour vous.',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: muted,
              height: 1.35,
            ),
          ),
          const SizedBox(height: MakoloSpacing.md),
          Text(
            'Rechercher des opportunités',
            style: theme.textTheme.titleSmall?.copyWith(
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: MakoloSpacing.sm),
          Semantics(
            label: 'Rechercher des opportunités',
            child: TextField(
              key: const Key('guest-home-query'),
              controller: _search,
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => _explore(),
              onTapOutside: (_) =>
                  FocusManager.instance.primaryFocus?.unfocus(),
              decoration: InputDecoration(
                hintText: 'Voyager, participer, trouver un service…',
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
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: MakoloSpacing.md,
                  vertical: MakoloSpacing.compact,
                ),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(MakoloRadii.card),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(MakoloRadii.card),
                  borderSide: BorderSide(color: colors.outlineVariant),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(MakoloRadii.card),
                  borderSide: BorderSide(color: colors.primary, width: 2),
                ),
              ),
            ),
          ),
          const SizedBox(height: MakoloSpacing.md),
          GridView.count(
            key: const Key('guest-home-quick-choices'),
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: MakoloSpacing.sm,
            crossAxisSpacing: MakoloSpacing.sm,
            childAspectRatio: 2.9,
            children: [
              _ExploreChoice(
                label: 'Voyager',
                icon: Icons.directions_bus_outlined,
                onPressed: () =>
                    _explore(vertical: 'transport', includeQuery: false),
              ),
              _ExploreChoice(
                label: 'Participer',
                icon: Icons.event_outlined,
                onPressed: () =>
                    _explore(vertical: 'event', includeQuery: false),
              ),
              _ExploreChoice(
                label: 'Être accompagné',
                icon: Icons.handshake_outlined,
                onPressed: () =>
                    _explore(vertical: 'service', includeQuery: false),
              ),
              _ExploreChoice(
                label: 'Tout explorer',
                icon: Icons.explore_outlined,
                onPressed: () => _explore(includeQuery: false),
              ),
            ],
          ),
          const SizedBox(height: MakoloSpacing.compact),
          Container(
            key: const Key('guest-home-action-journey'),
            padding: const EdgeInsets.symmetric(
              horizontal: MakoloSpacing.md,
              vertical: MakoloSpacing.md,
            ),
            decoration: BoxDecoration(
              color: colors.primary.withValues(alpha: 0.055),
              borderRadius: BorderRadius.circular(MakoloRadii.large),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Makolo vous accompagne jusqu’à l’action',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w800,
                    height: 1.2,
                  ),
                ),
                const SizedBox(height: MakoloSpacing.compact),
                Row(
                  children: [
                    const Expanded(
                      child: _JourneyStep(number: '01', label: 'Découvrez'),
                    ),
                    Icon(Icons.chevron_right_rounded, size: 18, color: muted),
                    const Expanded(
                      child: _JourneyStep(number: '02', label: 'Préparez'),
                    ),
                    Icon(Icons.chevron_right_rounded, size: 18, color: muted),
                    const Expanded(
                      child: _JourneyStep(number: '03', label: 'Avancez'),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: MakoloSpacing.md),
          Material(
            color: colors.surface,
            borderRadius: BorderRadius.circular(MakoloRadii.card),
            child: InkWell(
              key: const Key('guest-home-spaces'),
              onTap: () => context.go('/spaces'),
              borderRadius: BorderRadius.circular(MakoloRadii.card),
              child: Container(
                padding: const EdgeInsets.all(MakoloSpacing.md),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(MakoloRadii.card),
                  border: Border.all(color: colors.outlineVariant),
                ),
                child: Row(
                  children: [
                    Icon(
                      Icons.groups_outlined,
                      color: colors.primary,
                      size: 26,
                    ),
                    const SizedBox(width: MakoloSpacing.compact),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Les Espaces sur Makolo',
                            style: theme.textTheme.titleSmall?.copyWith(
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          const SizedBox(height: MakoloSpacing.xs),
                          Text(
                            'Organisations, équipes et communautés',
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: muted,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: MakoloSpacing.xs),
                    Icon(
                      Icons.arrow_forward_ios_rounded,
                      size: 16,
                      color: muted,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ExploreChoice extends StatelessWidget {
  const _ExploreChoice({
    required this.label,
    required this.icon,
    required this.onPressed,
  });

  final String label;
  final IconData icon;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;
    final accent = theme.brightness == Brightness.dark
        ? colors.secondary
        : colors.primary;
    return Material(
      color: colors.surface,
      shape: RoundedRectangleBorder(
        side: BorderSide(color: colors.outlineVariant),
        borderRadius: BorderRadius.circular(MakoloRadii.card),
      ),
      child: InkWell(
        onTap: onPressed,
        borderRadius: BorderRadius.circular(MakoloRadii.card),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: MakoloSpacing.sm),
          child: Row(
            children: [
              Icon(icon, size: 19, color: accent),
              const SizedBox(width: MakoloSpacing.sm),
              Expanded(
                child: Text(
                  label,
                  maxLines: 2,
                  style: theme.textTheme.labelMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                    height: 1.15,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _JourneyStep extends StatelessWidget {
  const _JourneyStep({required this.number, required this.label});

  final String number;
  final String label;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;
    final accent = theme.brightness == Brightness.dark
        ? colors.secondary
        : colors.primary;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Text(
          number,
          style: theme.textTheme.labelMedium?.copyWith(
            color: accent,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: MakoloSpacing.xs),
        Text(
          label,
          textAlign: TextAlign.center,
          style: theme.textTheme.labelMedium?.copyWith(
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    );
  }
}
