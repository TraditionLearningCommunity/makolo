import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../data/local/profile_store.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';
import '../../design/presentation_layout.dart';
import '../../design/surface_states.dart';
import '../../navigation/destination.dart';
import '../../navigation/refresh_boundary.dart';
import '../../presentation/contracts/now_presentation.dart';
import '../../repositories/personal_repository.dart';
import 'now_selector.dart';

class NowScreen extends StatelessWidget {
  const NowScreen({super.key, required this.repository, this.now});

  final PersonalRepository repository;
  final DateTime Function()? now;

  @override
  Widget build(BuildContext context) {
    return MakoloRefreshBoundary(
      child: StreamBuilder<StoredProjection?>(
        stream: repository.watchNow(),
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting &&
              !snapshot.hasData) {
            return const MakoloSurfaceStateView(
              state: MakoloSurfacePresentation(
                availability: MakoloAvailabilityCue.loading,
              ),
              content: SizedBox.shrink(),
            );
          }

          final projection = snapshot.data;
          if (projection == null) {
            return const MakoloEmptyState(
              title: 'Now n’est pas disponible pour le moment.',
              icon: Icons.adjust,
            );
          }

          final selection = const NowSelector().select(
            projection: projection,
            now: (now?.call() ?? DateTime.now()).toUtc(),
          );
          return NowView(
            selection: selection,
            onOpenOwner: (destination) => _openOwner(context, destination),
          );
        },
      ),
    );
  }

  void _openOwner(BuildContext context, StructuredDestination destination) {
    final path = ownerPathFor(destination);
    if (path != null) context.push(path);
  }

  static String? ownerPathFor(StructuredDestination destination) {
    final id = Uri.encodeComponent(destination.id);
    return switch (destination.kind.toLowerCase()) {
      'journey' => '/journeys/$id',
      _ => null,
    };
  }
}

class NowView extends StatefulWidget {
  const NowView({super.key, required this.selection, this.onOpenOwner});

  final NowSelection selection;
  final ValueChanged<StructuredDestination>? onOpenOwner;

  @override
  State<NowView> createState() => _NowViewState();
}

class _NowViewState extends State<NowView> {
  final ScrollController _fieldController = ScrollController();
  String? _selectedKey;

  @override
  void didUpdateWidget(covariant NowView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (_selectedKey != null &&
        !_situations.any((item) => _keyOf(item) == _selectedKey)) {
      _selectedKey = null;
    }
  }

  @override
  void dispose() {
    _fieldController.dispose();
    super.dispose();
  }

  List<NowSituationPresentation> get _situations => widget.selection.situations;

  NowSituationPresentation? get _selected {
    final key = _selectedKey;
    if (key == null) return null;
    for (final item in _situations) {
      if (_keyOf(item) == key) return item;
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final selected = _selected;
    final field = _NowField(
      situations: _situations,
      controller: _fieldController,
      selectedKey: _selectedKey,
      onSelect: _select,
      onOpenOwner: widget.onOpenOwner,
    );

    final content = selected == null
        ? MakoloContentFrame(
            maxContentWidth: MakoloLayout.calmMaxWidth,
            child: field,
          )
        : MakoloAdaptiveSplit(
            splitAt: MakoloLayout.nowFocusSplitMinWidth,
            field: MakoloContentFrame(child: field),
            focus: MakoloContentFrame(
              child: _NowDepth(
                situation: selected,
                onClose: _closeDepth,
                onOpenOwner: widget.onOpenOwner,
              ),
            ),
            narrow: MakoloContentFrame(
              maxContentWidth: MakoloLayout.calmMaxWidth,
              child: _NowDepth(
                situation: selected,
                onClose: _closeDepth,
                onOpenOwner: widget.onOpenOwner,
              ),
            ),
          );

    return PopScope<Object?>(
      canPop: _selected == null,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop && _selected != null) _closeDepth();
      },
      child: MakoloSurfaceStateView(
        state: widget.selection.state,
        empty: widget.selection.isCalm
            ? const _NowCalm()
            : const _NowUnavailable(),
        content: content,
      ),
    );
  }

  void _select(NowSituationPresentation situation) {
    setState(() => _selectedKey = _keyOf(situation));
  }

  void _closeDepth() {
    if (_selectedKey == null) return;
    setState(() => _selectedKey = null);
  }

  String _keyOf(NowSituationPresentation situation) => situation.identity;
}

class _NowField extends StatelessWidget {
  const _NowField({
    required this.situations,
    required this.controller,
    required this.selectedKey,
    required this.onSelect,
    required this.onOpenOwner,
  });

  final List<NowSituationPresentation> situations;
  final ScrollController controller;
  final String? selectedKey;
  final ValueChanged<NowSituationPresentation> onSelect;
  final ValueChanged<StructuredDestination>? onOpenOwner;

  @override
  Widget build(BuildContext context) {
    if (situations.isEmpty) return const _NowCalm();

    final primary = situations.first;
    final secondary = situations.skip(1).toList(growable: false);

    return ListView(
      key: const PageStorageKey<String>('now-field-scroll'),
      controller: controller,
      padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
      children: [
        _NowPrimarySituation(
          situation: primary,
          selected: selectedKey == _keyOf(primary),
          onSelect: () => onSelect(primary),
          onOpenOwner: onOpenOwner,
        ),
        if (secondary.isNotEmpty) ...[
          const SizedBox(height: MakoloSpacing.strong),
          Text(
            'Aussi maintenant',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: MakoloSpacing.md),
          for (var index = 0; index < secondary.length; index++) ...[
            _NowSecondarySituation(
              situation: secondary[index],
              onSelect: () => onSelect(secondary[index]),
            ),
            if (index != secondary.length - 1)
              const SizedBox(height: MakoloSpacing.md),
          ],
        ],
      ],
    );
  }

  String _keyOf(NowSituationPresentation situation) => situation.identity;
}

String _presentationKey(String value) => value
    .trim()
    .toLowerCase()
    .replaceAll(RegExp(r'\s+'), ' ')
    .replaceAll(RegExp(r'[.:;–—-]+$'), '')
    .trim();

bool _samePresentationText(String? left, String? right) {
  if (left == null || right == null) return false;
  return _presentationKey(left) == _presentationKey(right);
}

String? _distinctPresentationText(String? value, Iterable<String?> others) {
  final text = value?.trim();
  if (text == null || text.isEmpty) return null;
  for (final other in others) {
    if (_samePresentationText(text, other)) return null;
  }
  return text;
}

class _NowPrimarySituation extends StatelessWidget {
  const _NowPrimarySituation({
    required this.situation,
    required this.selected,
    required this.onSelect,
    required this.onOpenOwner,
  });

  final NowSituationPresentation situation;
  final bool selected;
  final VoidCallback onSelect;
  final ValueChanged<StructuredDestination>? onOpenOwner;

  @override
  Widget build(BuildContext context) {
    final ownerDestination = situation.ownerDestination;
    final ownerPath = ownerDestination == null
        ? null
        : NowScreen.ownerPathFor(ownerDestination);
    final canOpenOwner =
        situation.responseLabel != null &&
        ownerPath != null &&
        onOpenOwner != null;
    final contextLabel = _distinctPresentationText(situation.humanContext, [
      situation.meaning,
    ]);
    final whyNow = _distinctPresentationText(situation.whyNow, [
      situation.meaning,
      situation.humanContext,
    ]);
    return Semantics(
      container: true,
      button: true,
      selected: selected,
      label: [?contextLabel, situation.meaning, ?whyNow].join('. '),
      child: InkWell(
        onTap: onSelect,
        borderRadius: BorderRadius.circular(MakoloRadii.card),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.compact),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (contextLabel != null) ...[
                Text(
                  contextLabel,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: MakoloSpacing.sm),
              ],
              Text(
                situation.meaning,
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              if (whyNow != null) ...[
                const SizedBox(height: MakoloSpacing.md),
                Text(
                  whyNow,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
              if (situation.metadata.isNotEmpty) ...[
                const SizedBox(height: MakoloSpacing.md),
                MakoloMetadata(
                  items: [
                    for (final item in situation.metadata)
                      MakoloMetadataItem(item),
                  ],
                ),
              ],
              if (canOpenOwner) ...[
                const SizedBox(height: MakoloSpacing.lg),
                FilledButton(
                  onPressed: () => onOpenOwner!(ownerDestination!),
                  child: Text(situation.responseLabel ?? 'Ouvrir'),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _NowSecondarySituation extends StatelessWidget {
  const _NowSecondarySituation({
    required this.situation,
    required this.onSelect,
  });

  final NowSituationPresentation situation;
  final VoidCallback onSelect;

  @override
  Widget build(BuildContext context) {
    final contextLabel = _distinctPresentationText(situation.humanContext, [
      situation.meaning,
    ]);
    return MakoloCard(
      onTap: onSelect,
      semanticLabel: [
        ?contextLabel,
        situation.meaning,
        'Ouvrir le détail',
      ].join('. '),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (contextLabel != null) ...[
            Text(contextLabel, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: MakoloSpacing.sm),
          ],
          Text(
            situation.meaning,
            style: Theme.of(context).textTheme.titleLarge,
          ),
          if (situation.metadata.isNotEmpty) ...[
            const SizedBox(height: MakoloSpacing.sm),
            MakoloMetadata(
              items: [
                for (final item in situation.metadata) MakoloMetadataItem(item),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _NowDepth extends StatelessWidget {
  const _NowDepth({
    required this.situation,
    required this.onClose,
    required this.onOpenOwner,
  });

  final NowSituationPresentation situation;
  final VoidCallback onClose;
  final ValueChanged<StructuredDestination>? onOpenOwner;

  @override
  Widget build(BuildContext context) {
    final ownerDestination = situation.ownerDestination;
    final canOpenOwner =
        ownerDestination != null &&
        NowScreen.ownerPathFor(ownerDestination) != null &&
        situation.responseLabel != null &&
        onOpenOwner != null;
    final contextLabel = _distinctPresentationText(situation.humanContext, [
      situation.meaning,
    ]);
    final whyNow = _distinctPresentationText(situation.whyNow, [
      situation.meaning,
      situation.humanContext,
    ]);
    final consequence = _distinctPresentationText(situation.consequence, [
      situation.meaning,
      situation.whyNow,
    ]);

    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
      child: MakoloFocusPane(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: TextButton.icon(
                onPressed: onClose,
                icon: const Icon(Icons.arrow_back_rounded),
                label: const Text('Now'),
              ),
            ),
            const SizedBox(height: MakoloSpacing.md),
            if (contextLabel != null) ...[
              Text(
                contextLabel,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: MakoloSpacing.sm),
            ],
            Text(
              situation.meaning,
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            if (whyNow != null) ...[
              const SizedBox(height: MakoloSpacing.lg),
              MakoloSection(
                title: 'Pourquoi maintenant',
                padding: EdgeInsets.zero,
                child: Text(whyNow),
              ),
            ],
            if (consequence != null) ...[
              const SizedBox(height: MakoloSpacing.lg),
              MakoloSection(
                title: 'Conséquence',
                padding: EdgeInsets.zero,
                child: Text(consequence),
              ),
            ],
            if (situation.metadata.isNotEmpty) ...[
              const SizedBox(height: MakoloSpacing.lg),
              MakoloMetadata(
                items: [
                  for (final item in situation.metadata)
                    MakoloMetadataItem(item),
                ],
              ),
            ],
            if (canOpenOwner) ...[
              const SizedBox(height: MakoloSpacing.xl),
              OutlinedButton(
                onPressed: () => onOpenOwner!(ownerDestination!),
                child: Text(situation.responseLabel ?? 'Ouvrir la démarche'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _NowUnavailable extends StatelessWidget {
  const _NowUnavailable();

  @override
  Widget build(BuildContext context) {
    return const MakoloContentFrame(
      child: Center(
        child: Padding(
          padding: EdgeInsets.all(MakoloSpacing.inner),
          child: Text('Now n’est pas disponible pour le moment.'),
        ),
      ),
    );
  }
}

class _NowCalm extends StatelessWidget {
  const _NowCalm();

  @override
  Widget build(BuildContext context) {
    return MakoloContentFrame(
      maxContentWidth: MakoloLayout.calmMaxWidth,
      child: ListView(
        padding: const EdgeInsets.symmetric(
          vertical: MakoloSpacing.exceptional,
        ),
        children: [
          Text(
            'Tout est en ordre. ✓',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.headlineMedium,
          ),
        ],
      ),
    );
  }
}
