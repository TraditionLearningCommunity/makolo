import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../design/makolo_components.dart';
import '../../design/makolo_patterns.dart';
import '../../design/makolo_theme.dart';
import '../../design/presentation_layout.dart';
import '../../design/presentation_media.dart';
import '../../design/surface_states.dart';
import '../scenarios/presentation_fixture_resolver.dart';
import '../scenarios/now_scenarios.dart';
import '../scenarios/presentation_scenarios.dart';

enum _GalleryCategory { foundations, primitives, patterns, states, scenarios }

class PresentationGalleryApp extends StatefulWidget {
  const PresentationGalleryApp({super.key});

  @override
  State<PresentationGalleryApp> createState() => _PresentationGalleryAppState();
}

class _PresentationGalleryAppState extends State<PresentationGalleryApp> {
  ThemeMode _themeMode = ThemeMode.light;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: buildMakoloLightTheme(),
      darkTheme: buildMakoloDarkTheme(),
      themeMode: _themeMode,
      home: PresentationGallery(
        dark: _themeMode == ThemeMode.dark,
        onToggleTheme: () => setState(() {
          _themeMode = _themeMode == ThemeMode.dark
              ? ThemeMode.light
              : ThemeMode.dark;
        }),
      ),
    );
  }
}

class PresentationGallery extends StatefulWidget {
  const PresentationGallery({
    super.key,
    required this.dark,
    required this.onToggleTheme,
  });

  final bool dark;
  final VoidCallback onToggleTheme;

  @override
  State<PresentationGallery> createState() => _PresentationGalleryState();
}

class _PresentationGalleryState extends State<PresentationGallery> {
  static const _viewports = <Size>[
    Size(360, 800),
    Size(430, 932),
    Size(834, 1112),
    Size(840, 1112),
    Size(880, 1112),
    Size(900, 1112),
    Size(960, 900),
    Size(1040, 900),
    Size(1200, 900),
    Size(1440, 900),
    Size(1728, 1117),
  ];
  static const _textScales = <double>[1, 1.3, 1.6];

  _GalleryCategory _category = _GalleryCategory.foundations;
  int _viewportIndex = 0;
  int _textScaleIndex = 0;
  bool _reduceMotion = false;
  String _scenarioId = PresentationScenarioCatalog.all.first.id;

  void _cycleViewport() =>
      setState(() => _viewportIndex = (_viewportIndex + 1) % _viewports.length);

  void _cycleTextScale() => setState(
    () => _textScaleIndex = (_textScaleIndex + 1) % _textScales.length,
  );

  @override
  Widget build(BuildContext context) {
    final viewport = _viewports[_viewportIndex];
    final textScale = _textScales[_textScaleIndex];

    return Scaffold(
      appBar: AppBar(title: const Text('Makolo Presentation Gallery')),
      body: Column(
        children: [
          _GalleryControls(
            category: _category,
            dark: widget.dark,
            viewport: viewport,
            textScale: textScale,
            reduceMotion: _reduceMotion,
            scenarioId: _scenarioId,
            onCategoryChanged: (value) => setState(() => _category = value),
            onToggleTheme: widget.onToggleTheme,
            onCycleViewport: _cycleViewport,
            onCycleTextScale: _cycleTextScale,
            onReduceMotionChanged: (value) =>
                setState(() => _reduceMotion = value),
            onScenarioChanged: (value) => setState(() => _scenarioId = value),
          ),
          const Divider(height: 1),
          Expanded(
            child: Center(
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.all(MakoloSpacing.md),
                child: SizedBox(
                  width: viewport.width,
                  height: math.min(viewport.height, 720.0),
                  child: MediaQuery(
                    data: MediaQueryData(
                      size: viewport,
                      textScaler: TextScaler.linear(textScale),
                      disableAnimations: _reduceMotion,
                    ),
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        color: context.makoloSurfaces.canvas,
                        border: Border.all(
                          color: context.makoloSurfaces.border,
                        ),
                      ),
                      child: _GalleryPreview(
                        category: _category,
                        scenarioId: _scenarioId,
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _GalleryControls extends StatelessWidget {
  const _GalleryControls({
    required this.category,
    required this.dark,
    required this.viewport,
    required this.textScale,
    required this.reduceMotion,
    required this.scenarioId,
    required this.onCategoryChanged,
    required this.onToggleTheme,
    required this.onCycleViewport,
    required this.onCycleTextScale,
    required this.onReduceMotionChanged,
    required this.onScenarioChanged,
  });

  final _GalleryCategory category;
  final bool dark;
  final Size viewport;
  final double textScale;
  final bool reduceMotion;
  final String scenarioId;
  final ValueChanged<_GalleryCategory> onCategoryChanged;
  final VoidCallback onToggleTheme;
  final VoidCallback onCycleViewport;
  final VoidCallback onCycleTextScale;
  final ValueChanged<bool> onReduceMotionChanged;
  final ValueChanged<String> onScenarioChanged;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(MakoloSpacing.sm),
      child: Wrap(
        crossAxisAlignment: WrapCrossAlignment.center,
        spacing: MakoloSpacing.sm,
        runSpacing: MakoloSpacing.sm,
        children: [
          DropdownButton<_GalleryCategory>(
            key: const Key('gallery-category'),
            value: category,
            items: [
              for (final value in _GalleryCategory.values)
                DropdownMenuItem(
                  value: value,
                  child: Text(switch (value) {
                    _GalleryCategory.foundations => 'Foundations',
                    _GalleryCategory.primitives => 'Primitives',
                    _GalleryCategory.patterns => 'Patterns',
                    _GalleryCategory.states => 'States',
                    _GalleryCategory.scenarios => 'Scenario Catalog',
                  }),
                ),
            ],
            onChanged: (value) {
              if (value != null) onCategoryChanged(value);
            },
          ),
          OutlinedButton(
            key: const Key('gallery-theme-toggle'),
            onPressed: onToggleTheme,
            child: Text(dark ? 'Light' : 'Dark'),
          ),
          OutlinedButton(
            key: const Key('gallery-viewport-cycle'),
            onPressed: onCycleViewport,
            child: Text('${viewport.width.toInt()}×${viewport.height.toInt()}'),
          ),
          OutlinedButton(
            key: const Key('gallery-text-scale-cycle'),
            onPressed: onCycleTextScale,
            child: Text('Text ${textScale.toStringAsFixed(1)}'),
          ),
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('Reduce motion'),
              Switch(
                key: const Key('gallery-reduce-motion'),
                value: reduceMotion,
                onChanged: onReduceMotionChanged,
              ),
            ],
          ),
          DropdownButton<String>(
            key: const Key('gallery-scenario'),
            value: scenarioId,
            items: [
              for (final scenario in PresentationScenarioCatalog.all)
                DropdownMenuItem(value: scenario.id, child: Text(scenario.id)),
            ],
            onChanged: (value) {
              if (value != null) onScenarioChanged(value);
            },
          ),
        ],
      ),
    );
  }
}

class _GalleryPreview extends StatelessWidget {
  const _GalleryPreview({required this.category, required this.scenarioId});

  final _GalleryCategory category;
  final String scenarioId;

  @override
  Widget build(BuildContext context) {
    return switch (category) {
      _GalleryCategory.foundations => const _FoundationsPreview(),
      _GalleryCategory.primitives => const _PrimitivesPreview(),
      _GalleryCategory.patterns => const _PatternsPreview(),
      _GalleryCategory.states => const _StatesPreview(),
      _GalleryCategory.scenarios => _ScenarioPreview(scenarioId: scenarioId),
    };
  }
}

class _FoundationsPreview extends StatelessWidget {
  const _FoundationsPreview();

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: MakoloContentFrame(
        maxContentWidth: MakoloLayout.readingMaxWidth,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Presentation',
                style: Theme.of(context).textTheme.headlineLarge,
              ),
              const SizedBox(height: MakoloSpacing.lg),
              const MakoloCard(
                child: Text(
                  'Même vérité, même priorité, géométrie adaptée à l’espace disponible.',
                ),
              ),
              const SizedBox(height: MakoloLayout.sectionMajor),
              const MakoloStatus(
                label: 'Fondation partagée',
                tone: MakoloStatusTone.info,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PrimitivesPreview extends StatelessWidget {
  const _PrimitivesPreview();

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(MakoloSpacing.md),
      child: Column(
        children: [
          MakoloAdaptiveGrid(
            children: [
              MakoloMediaFrame(
                aspect: MakoloMediaAspect.standard,
                child: FixtureMediaResolver.resolve(
                  'fixture://discover/data-science-nairobi',
                ),
              ),
              const SizedBox(
                height: 220,
                child: MakoloSpatialFrame(
                  spatial: FixtureSpatialCanvas(),
                  compactFallback: MakoloMediaPlaceholder(
                    label: 'Carte disponible en profondeur',
                    icon: Icons.map_outlined,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: MakoloSpacing.lg),
          const MakoloAdaptiveSplit(
            splitAt: MakoloLayout.ongoingSplitMinWidth,
            field: MakoloCard(child: Text('Field')),
            focus: MakoloCard(child: Text('Focus / Depth')),
          ),
        ],
      ),
    );
  }
}

class _PatternsPreview extends StatelessWidget {
  const _PatternsPreview();

  @override
  Widget build(BuildContext context) {
    return const SingleChildScrollView(
      padding: EdgeInsets.all(MakoloSpacing.md),
      child: Column(
        children: [
          MakoloAttentionBlock(
            title: 'Une vérification est nécessaire',
            body: 'La vérité déjà disponible reste visible.',
          ),
          SizedBox(height: MakoloSpacing.lg),
          MakoloTimeline(
            items: [
              MakoloTimelineItem(title: 'Préparé', completed: true),
              MakoloTimelineItem(title: 'Confirmation distante', current: true),
            ],
          ),
        ],
      ),
    );
  }
}

class _StatesPreview extends StatelessWidget {
  const _StatesPreview();

  @override
  Widget build(BuildContext context) {
    return SizedBox.expand(
      child: MakoloSurfaceStateView(
        state: const MakoloSurfacePresentation(
          availability: MakoloAvailabilityCue.content,
          freshness: MakoloFreshnessCue.oldObservation,
          reachability: MakoloReachabilityCue.temporarilyUnavailable,
          commit: MakoloCommitCue.pending,
          refreshing: true,
        ),
        content: ListView(
          padding: const EdgeInsets.all(MakoloSpacing.md),
          children: const [
            MakoloCard(
              child: Text(
                'Le contenu connu reste disponible pendant la reprise.',
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ScenarioPreview extends StatelessWidget {
  const _ScenarioPreview({required this.scenarioId});

  final String scenarioId;

  @override
  Widget build(BuildContext context) {
    final scenario = PresentationScenarioCatalog.byId(scenarioId);
    if (scenario.surface == 'now') {
      return NowGalleryScenarioPreview(id: scenarioId);
    }
    return SingleChildScrollView(
      padding: const EdgeInsets.all(MakoloSpacing.md),
      child: MakoloCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(scenario.id, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: MakoloSpacing.sm),
            Text('Surface : ${scenario.surface}'),
            const SizedBox(height: MakoloSpacing.sm),
            MakoloStatus(
              label:
                  scenario.dataKind ==
                      PresentationScenarioDataKind.runtimeCompatible
                  ? 'Runtime-compatible'
                  : 'Target Presentation',
            ),
            const SizedBox(height: MakoloSpacing.lg),
            const Text(
              'Le catalogue prépare les cas de test sans implémenter ici l’écran final.',
            ),
          ],
        ),
      ),
    );
  }
}
