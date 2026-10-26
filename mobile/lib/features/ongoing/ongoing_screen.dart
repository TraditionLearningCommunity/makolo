import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../data/local/profile_store.dart';
import '../../app/sync_lifecycle.dart';
import '../../sync/owner_source_state.dart';
import '../../sync/sync_status.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_patterns.dart';
import '../../design/makolo_theme.dart';
import '../../design/presentation_layout.dart';
import '../../design/surface_states.dart';
import '../../navigation/refresh_boundary.dart';
import '../../navigation/deep_link_resolver.dart';
import '../../navigation/destination.dart';
import '../../presentation/humanization.dart';
import '../../repositories/personal_repository.dart';
import '../../network/makolo_api_client.dart';
import 'ongoing_presentation.dart';

class OngoingScreen extends StatefulWidget {
  const OngoingScreen({
    super.key,
    required this.repository,
    this.projectionStream,
    this.baseUri,
    this.api,
  });
  final PersonalRepository repository;
  final Stream<StoredProjection?>? projectionStream;
  final Uri? baseUri;
  final MakoloApiClient? api;
  @override
  State<OngoingScreen> createState() => _OngoingScreenState();
}

class _OngoingScreenState extends State<OngoingScreen> {
  String? _selectedOwnerKey;
  StoredProjection? _lastProjection;
  bool _loadingMore = false;
  String? _moreError;
  late Stream<StoredProjection?> _projectionStream;
  late Stream<OwnerSourceState> _sourceStream;

  @override
  void initState() {
    super.initState();
    _bindStreams();
  }

  @override
  void didUpdateWidget(covariant OngoingScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.repository != widget.repository ||
        oldWidget.projectionStream != widget.projectionStream) {
      _lastProjection = null;
      _loadingMore = false;
      _moreError = null;
      _bindStreams();
    }
  }

  void _bindStreams() {
    _projectionStream =
        widget.projectionStream ?? widget.repository.watchOngoing();
    _sourceStream = widget.projectionStream == null
        ? widget.repository.watchOngoingSource()
        : const Stream<OwnerSourceState>.empty();
  }

  void _select(OngoingContinuityPresentation item) =>
      setState(() => _selectedOwnerKey = _ownerKey(item));
  void _clearSelection() => setState(() => _selectedOwnerKey = null);

  String _ownerKey(OngoingContinuityPresentation item) => item.id;

  Future<void> _loadMore() async {
    final current = _lastProjection;
    final api = widget.api;
    if (_loadingMore || current == null || api == null) return;
    setState(() {
      _loadingMore = true;
      _moreError = null;
    });
    try {
      await widget.repository.loadMoreOngoing(api: api, current: current);
    } on Object {
      if (mounted) {
        setState(() => _moreError = 'La suite n’a pas pu être chargée.');
      }
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }


  @override
  Widget build(BuildContext context) => MakoloRefreshBoundary(
    child: StreamBuilder<OwnerSourceState>(
      stream: _sourceStream,
      initialData: OwnerSourceState.unknown,
      builder: (context, sourceSnapshot) => StreamBuilder<StoredProjection?>(
        stream: _projectionStream,
        builder: (context, snapshot) {
          if (!snapshot.hasError &&
              snapshot.connectionState == ConnectionState.active) {
            _lastProjection = snapshot.data;
          }
          final projection = snapshot.data ?? _lastProjection;
          final syncStatus = SyncStatusScope.maybeOf(context);
          if (projection == null &&
              (snapshot.hasError ||
                  sourceSnapshot.hasError ||
                  sourceSnapshot.data?.lastErrorCode != null ||
                  syncStatus?.state == SyncVisualState.failed)) {
            return MakoloErrorState(
              message: 'En cours indisponible.',
              preservedMessage: '',
              onRetry: () => SyncRefreshScope.maybeOf(context)?.refresh(),
            );
          }
          if (projection == null &&
              (syncStatus?.state == SyncVisualState.syncing ||
                  snapshot.connectionState == ConnectionState.waiting)) {
            return const MakoloSurfaceStateView(
              state: MakoloSurfacePresentation(
                availability: MakoloAvailabilityCue.loading,
              ),
              content: SizedBox.shrink(),
            );
          }
          if (projection == null) {
            return const MakoloSurfaceStateView(
              state: MakoloSurfacePresentation(
                availability: MakoloAvailabilityCue.empty,
              ),
              empty: MakoloEmptyState(
                title: 'En cours indisponible.',
                body: 'Vos informations ne sont pas encore disponibles sur cet appareil.',
              ),
              content: SizedBox.shrink(),
            );
          }
          final items = OngoingContinuityPresentation.fromProjection(
            projection,
          );
          if (items.isEmpty) {
            return MakoloSurfaceStateView(
              state: MakoloSurfacePresentation(
                availability: MakoloAvailabilityCue.empty,
                failure: sourceSnapshot.data?.lastErrorCode == null
                    ? MakoloFailureCue.none
                    : MakoloFailureCue.recoverable,
              ),
              recoverableErrorMessage: 'Actualisation impossible.',
              preservedMessage: '',
              onRetry: () => SyncRefreshScope.maybeOf(context)?.refresh(),
              empty: const MakoloEmptyState(title: 'Rien en cours pour le moment.'),
              content: const SizedBox.shrink(),
            );
          }
          final matches = items.where(
            (item) => _ownerKey(item) == _selectedOwnerKey,
          );
          final selected = matches.isEmpty ? null : matches.first;
          final cursor = projection.payload['continuation'];
          final moreToken = cursor is Map ? cursor['token'] : null;
          final stale =
              projection.freshUntil != null &&
              projection.freshUntil!.isBefore(DateTime.now().toUtc());
          return MakoloSurfaceStateView(
            state: MakoloSurfacePresentation(
              availability: MakoloAvailabilityCue.content,
              freshness: stale
                  ? MakoloFreshnessCue.oldObservation
                  : MakoloFreshnessCue.current,
              failure:
                  snapshot.hasError ||
                      sourceSnapshot.data?.lastErrorCode != null
                  ? MakoloFailureCue.recoverable
                  : MakoloFailureCue.none,
            ),
            // Keep existing journeys visible without an additional banner.
            recoverableErrorMessage: null,
            preservedMessage: '',
            onRetry: () => SyncRefreshScope.maybeOf(context)?.refresh(),
            content: _OngoingAdaptiveView(
              items: items,
              selected: selected,
              stale: stale,
              onSelect: _select,
              onBack: _clearSelection,
              baseUri: widget.baseUri,
              api: widget.api,
              onMore: widget.api != null && moreToken is String && moreToken.isNotEmpty
                  ? () { _loadMore(); }
                  : null,
              moreBusy: _loadingMore,
              moreError: _moreError,
              endReached: cursor is Map && cursor['state'] == 'end',
            ),
          );
        },
      ),
    ),
  );
}

class _OngoingAdaptiveView extends StatelessWidget {
  const _OngoingAdaptiveView({
    required this.items,
    required this.selected,
    required this.stale,
    required this.onSelect,
    required this.onBack,
    this.baseUri,
    this.api,
    this.onMore,
    this.moreBusy = false,
    this.moreError,
    this.endReached = false,
  });
  final List<OngoingContinuityPresentation> items;
  final OngoingContinuityPresentation? selected;
  final bool stale;
  final ValueChanged<OngoingContinuityPresentation> onSelect;
  final VoidCallback onBack;
  final Uri? baseUri;
  final MakoloApiClient? api;
  final VoidCallback? onMore;
  final bool moreBusy;
  final String? moreError;
  final bool endReached;

  @override
  Widget build(BuildContext context) => MakoloContentFrame(
    maxContentWidth: 1040,
    child: MakoloAdaptiveSplit(
      splitAt: MakoloLayout.ongoingSplitMinWidth,
      field: _OngoingField(
        items: items,
        selected: selected,
        stale: stale,
        onSelect: onSelect,
        baseUri: baseUri,
        api: api,
        onMore: onMore,
        moreBusy: moreBusy,
        moreError: moreError,
        endReached: endReached,
      ),
      focus: selected == null
          ? const _OngoingFocusPlaceholder()
          : _OngoingFocus(item: selected!, onBack: onBack),
      narrow: selected == null
          ? _OngoingField(
              items: items,
              selected: selected,
              stale: stale,
              onSelect: onSelect,
              baseUri: baseUri,
              api: api,
              onMore: onMore,
              moreBusy: moreBusy,
              moreError: moreError,
              endReached: endReached,
            )
          : _OngoingFocus(item: selected!, onBack: onBack),
    ),
  );
}

class _OngoingField extends StatefulWidget {
  const _OngoingField({
    required this.items,
    required this.selected,
    required this.stale,
    required this.onSelect,
    this.baseUri,
    this.api,
    this.onMore,
    this.moreBusy = false,
    this.moreError,
    this.endReached = false,
  });

  final List<OngoingContinuityPresentation> items;
  final OngoingContinuityPresentation? selected;
  final bool stale;
  final ValueChanged<OngoingContinuityPresentation> onSelect;
  final Uri? baseUri;
  final MakoloApiClient? api;
  final VoidCallback? onMore;
  final bool moreBusy;
  final String? moreError;
  final bool endReached;

  @override
  State<_OngoingField> createState() => _OngoingFieldState();
}

class _OngoingFieldState extends State<_OngoingField> {
  final ScrollController _scroll = ScrollController();
  final Set<String> _expanded = <String>{};

  @override
  void initState() {
    super.initState();
    _scroll.addListener(_maybeMore);
    WidgetsBinding.instance.addPostFrameCallback((_) => _maybeMore());
  }

  @override
  void didUpdateWidget(covariant _OngoingField oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.items.length != widget.items.length ||
        oldWidget.moreBusy != widget.moreBusy ||
        oldWidget.moreError != widget.moreError) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _maybeMore());
    }
  }

  void _maybeMore() {
    if (!mounted || !_scroll.hasClients ||
        widget.moreBusy || widget.moreError != null ||
        widget.onMore == null) return;
    if (_scroll.position.extentAfter < 480) widget.onMore?.call();
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ListView.separated(
    controller: _scroll,
    key: const PageStorageKey<String>('ongoing-field'),
    padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.lg),
    itemCount: widget.items.length + 1,
    separatorBuilder: (_, _) => const SizedBox(height: MakoloSpacing.lg),
    itemBuilder: (context, index) {
      if (index == widget.items.length) {
        if (widget.moreError != null) {
          return Center(
            child: TextButton.icon(
              onPressed: widget.onMore,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('Réessayer'),
            ),
          );
        }
        if (widget.moreBusy) {
          return const Center(child: Padding(
            padding: EdgeInsets.all(MakoloSpacing.md),
            child: CircularProgressIndicator.adaptive(),
          ));
        }
        if (widget.endReached && !widget.stale && widget.items.isNotEmpty) {
          return const Center(child: Padding(
            padding: EdgeInsets.all(MakoloSpacing.md),
            child: Text('Tout est affiché.'),
          ));
        }
        return const SizedBox(height: MakoloSpacing.xl);
      }
      final item = widget.items[index];
      final expanded = _expanded.contains(item.id);
      final hasDetail = item.settled.isNotEmpty || item.mySide.isNotEmpty ||
          item.elsewhere.isNotEmpty || item.next.isNotEmpty ||
          item.blocker != null || item.waiting != null;
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _OngoingRow(
            item: item,
            selected: item.id == widget.selected?.id,
            stale: widget.stale,
            onTap: () => widget.onSelect(item),
            baseUri: widget.baseUri,
            api: widget.api,
          ),
          if (hasDetail) ...[
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: TextButton.icon(
                onPressed: () => setState(() {
                  if (!_expanded.add(item.id)) _expanded.remove(item.id);
                }),
                icon: Icon(expanded
                    ? Icons.expand_less_rounded
                    : Icons.expand_more_rounded),
                label: Text(expanded ? 'Voir moins' : 'Voir plus'),
              ),
            ),
            if (expanded) _OngoingN1Details(item: item),
          ],
        ],
      );
    },
  );
}

class _OngoingN1Details extends StatelessWidget {
  const _OngoingN1Details({required this.item});
  final OngoingContinuityPresentation item;

  String? get _ownerRoute {
    final kind = item.ownerKind;
    final id = item.ownerId;
    if (kind == null || id == null) return null;
    final chunks = id.split('-');
    if (chunks.length != 5 ||
        chunks[0].length != 8 ||
        chunks[1].length != 4 ||
        chunks[2].length != 4 ||
        chunks[3].length != 4 ||
        chunks[4].length != 12 ||
        id.replaceAll('-', '').split('').any(
          (character) => !'0123456789abcdefABCDEF'.contains(character),
        )) {
      return null;
    }
    final canOpen = item.capabilities.contains('open_detail') ||
        (kind == 'access' && item.capabilities.contains('open_access'));
    if (!canOpen) return null;
    return const DeepLinkResolver().resolve(
      StructuredDestination(kind: kind, id: Uri.encodeComponent(id)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final groups = <(String, List<String>)>[
      ('Déjà réglé', item.settled),
      ('De votre côté', item.mySide),
      ('En attente', item.elsewhere),
      ('Préparé par Makolo', item.makolo),
      ('À suivre', item.next),
      if (item.blocker != null) ('Ce qui bloque', [item.blocker!]),
    ];
    final seen = <String>{
      _ongoingKey(item.title), _ongoingKey(item.synthesis),
    };
    final nativeOwnerRoute = _ownerRoute;
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        MakoloSpacing.compact, 0, MakoloSpacing.compact, MakoloSpacing.md,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final (label, values) in groups)
            if (values.any((value) => value.trim().isNotEmpty &&
                !seen.contains(_ongoingKey(value)))) ...[
              const SizedBox(height: MakoloSpacing.sm),
              Text(label, style: Theme.of(context).textTheme.titleSmall),
              for (final value in values)
                if (value.trim().isNotEmpty &&
                    !_ongoingRedundant(value, item) &&
                    seen.add(_ongoingKey(value)))
                  Padding(
                    padding: const EdgeInsets.only(top: MakoloSpacing.xs),
                    child: Text(value, style: Theme.of(context).textTheme.bodyMedium),
                  ),
            ],
          if (nativeOwnerRoute != null) ...[
            const SizedBox(height: MakoloSpacing.md),
            FilledButton(
              onPressed: () => context.push(nativeOwnerRoute),
              child: const Text('Ouvrir la démarche'),
            ),
          ],
        ],
      ),
    );
  }
}

String _ongoingKey(String value) => value
    .trim()
    .toLowerCase()
    .replaceAll(RegExp(r'\s+'), ' ')
    .replaceAll(RegExp(r'[.:;–—-]+$'), '')
    .trim();

bool _sameOngoingText(String? left, String? right) {
  if (left == null || right == null) return false;
  return _ongoingKey(left) == _ongoingKey(right);
}

String? _ongoingSummary(String title, String synthesis) {
  final value = synthesis.trim();
  if (value.isEmpty || _sameOngoingText(value, title)) return null;
  for (final entry in const <(String, String)>[
    ('confirmer :', 'À confirmer'),
    ('confirmer:', 'À confirmer'),
    ('vérifier :', 'À vérifier'),
    ('vérifier:', 'À vérifier'),
  ]) {
    if (value.toLowerCase().startsWith(entry.$1)) {
      final tail = value.substring(entry.$1.length).trim();
      if (_sameOngoingText(tail, title)) return entry.$2;
    }
  }
  return value;
}

bool _ongoingRedundant(String value, OngoingContinuityPresentation item) {
  if (_sameOngoingText(value, item.title) ||
      _sameOngoingText(value, item.synthesis)) {
    return true;
  }
  final reduced = _ongoingSummary(item.title, value);
  return reduced == 'À confirmer' || reduced == 'À vérifier';
}

/// Published N1 images are delivered by the same API origin that owns the
/// projection. No third-party tracking URL or client-generated picture.
String? ongoingRecognitionImageUrl(String? source, Uri? baseUri) {
  final value = source?.trim();
  if (value == null || value.isEmpty) return null;
  final raw = Uri.tryParse(value);
  if (raw == null) return null;
  final resolved = raw.hasScheme ? raw : baseUri?.resolveUri(raw);
  if (resolved == null ||
      (resolved.scheme != 'http' && resolved.scheme != 'https') ||
      resolved.host.isEmpty ||
      (baseUri != null && resolved.origin != baseUri.origin)) {
    return null;
  }
  return resolved.toString();
}

class _OngoingProtectedImage extends StatefulWidget {
  const _OngoingProtectedImage({
    super.key,
    required this.api,
    required this.imageUrl,
    required this.label,
  });
  final MakoloApiClient api;
  final String imageUrl;
  final String label;
  @override
  State<_OngoingProtectedImage> createState() => _OngoingProtectedImageState();
}

class _OngoingProtectedImageState extends State<_OngoingProtectedImage> {
  late Future<Uint8List> _bytes;
  @override
  void initState() {
    super.initState();
    _load();
  }
  @override
  void didUpdateWidget(covariant _OngoingProtectedImage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.imageUrl != widget.imageUrl || oldWidget.api != widget.api) {
      _load();
    }
  }
  void _load() {
    _bytes = widget.api.getPresentationImage(Uri.parse(widget.imageUrl).path);
  }
  @override
  Widget build(BuildContext context) => FutureBuilder<Uint8List>(
    key: ValueKey(widget.imageUrl),
    future: _bytes,
    builder: (context, snapshot) {
      if (snapshot.hasData) {
        return Image.memory(
          snapshot.data!,
          fit: BoxFit.cover,
          semanticLabel: widget.label,
          gaplessPlayback: false,
          errorBuilder: (context, error, stackTrace) =>
              const Center(child: Icon(Icons.image_not_supported_outlined)),
        );
      }
      if (snapshot.hasError) {
        return const Center(child: Icon(Icons.image_not_supported_outlined));
      }
      return const Center(
        child: SizedBox(
          width: 20, height: 20,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      );
    },
  );
}

class _OngoingRow extends StatelessWidget {
  const _OngoingRow({
    required this.item,
    required this.selected,
    required this.stale,
    required this.onTap,
    this.baseUri,
    this.api,
  });
  final OngoingContinuityPresentation item;
  final bool selected;
  final bool stale;
  final VoidCallback onTap;
  final Uri? baseUri;
  final MakoloApiClient? api;

  String? _supportingLine() {
    final candidate = item.supporting ??
        (item.mySide.isNotEmpty
            ? item.mySide.first
            : item.next.isNotEmpty
                ? item.next.first
                : null);
    if (candidate == null || _ongoingRedundant(candidate, item)) return null;
    return candidate;
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.makoloSurfaces;
    final summary = _ongoingSummary(item.title, item.synthesis);
    final supporting = _supportingLine();
    final imageUrl = ongoingRecognitionImageUrl(item.mediaUrl, baseUri);
    final cue = item.cue;
    final cueColor = switch (item.cueTone) {
      'action' => colors.brand,
      'attention' => MakoloColors.pulse,
      'ready' => colors.success,
      _ => Theme.of(context).colorScheme.onSurfaceVariant,
    };
    final textTheme = Theme.of(context).textTheme;
    return Semantics(
      button: true,
      selected: selected,
      label: [
        item.title,
        ?summary,
        ?supporting,
      ].join('. '),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(MakoloRadii.large),
        child: AnimatedContainer(
          duration: MakoloMotion.effective(context, MakoloMotion.short),
          padding: const EdgeInsets.all(MakoloSpacing.compact),
          decoration: BoxDecoration(
            color: colors.surface,
            borderRadius: BorderRadius.circular(MakoloRadii.large),
            border: Border.all(
              color: selected ? colors.brand : colors.border,
              width: selected ? 1.5 : 1,
            ),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (imageUrl != null) ...[
                ClipRRect(
                  borderRadius: BorderRadius.circular(MakoloRadii.card),
                  child: SizedBox(
                    width: 92,
                    height: 108,
                    child: api == null
                        ? Image.network(
                            imageUrl,
                            key: const Key('ongoing-n1-recognition-media'),
                            fit: BoxFit.cover,
                            semanticLabel: item.mediaAlt ?? item.title,
                            errorBuilder: (context, error, stackTrace) =>
                                const Center(child: Icon(Icons.image_not_supported_outlined)),
                          )
                        : _OngoingProtectedImage(
                            key: const Key('ongoing-n1-recognition-media'),
                            api: api!,
                            imageUrl: imageUrl,
                            label: item.mediaAlt ?? item.title,
                          ),
                  ),
                ),
                const SizedBox(width: MakoloSpacing.compact),
              ],
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (cue != null || item.whenLabel != null) ...[
                      Wrap(
                        spacing: MakoloSpacing.sm,
                        runSpacing: MakoloSpacing.xs,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          if (cue != null)
                            DecoratedBox(
                              decoration: BoxDecoration(
                                color: cueColor.withValues(alpha: 0.09),
                                borderRadius: BorderRadius.circular(
                                  MakoloRadii.pill,
                                ),
                              ),
                              child: Padding(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: MakoloSpacing.sm,
                                  vertical: MakoloSpacing.xs,
                                ),
                                child: Text(
                                  cue,
                                  style: textTheme.labelSmall?.copyWith(
                                    color: cueColor,
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                              ),
                            ),
                          if (item.whenLabel != null)
                            Text(
                              item.whenLabel!,
                              style: textTheme.labelSmall?.copyWith(
                                color: Theme.of(context)
                                    .colorScheme.onSurfaceVariant,
                              ),
                            ),
                        ],
                      ),
                      const SizedBox(height: MakoloSpacing.sm),
                    ],
                    Text(
                      item.title,
                      style: textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w800,
                        letterSpacing: -0.25,
                      ),
                    ),
                    if (summary != null) ...[
                      const SizedBox(height: MakoloSpacing.xs),
                      Text(
                        summary,
                        style: textTheme.bodyMedium?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                    if (supporting != null) ...[
                      const SizedBox(height: MakoloSpacing.sm),
                      Text(
                        supporting,
                        style: textTheme.bodySmall?.copyWith(
                          color: colors.brand,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                    if (item.placeLabel != null) ...[
                      const SizedBox(height: MakoloSpacing.sm),
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.place_outlined,
                              size: 14,
                              color: Theme.of(context).colorScheme.onSurfaceVariant),
                          const SizedBox(width: MakoloSpacing.xs),
                          Flexible(
                            child: Text(
                              item.placeLabel!,
                              style: textTheme.bodySmall?.copyWith(
                                color: Theme.of(context)
                                    .colorScheme.onSurfaceVariant,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                    if (stale) ...[
                      const SizedBox(height: MakoloSpacing.sm),
                      Text(
                        'Dernière information connue',
                        style: textTheme.bodySmall,
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(width: MakoloSpacing.xs),
              Padding(
                padding: const EdgeInsets.only(top: MakoloSpacing.inner),
                child: Icon(
                  Icons.chevron_right_rounded,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                  size: 20,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _OngoingFocusPlaceholder extends StatelessWidget {
  const _OngoingFocusPlaceholder();
  @override
  Widget build(BuildContext context) => const MakoloFocusPane(
    child: Padding(
      padding: EdgeInsets.all(MakoloSpacing.lg),
      child: Text('Choisissez une démarche.'),
    ),
  );
}

class _OngoingFocus extends StatelessWidget {
  const _OngoingFocus({required this.item, required this.onBack});

  final OngoingContinuityPresentation item;
  final VoidCallback onBack;

  bool get _hasStructuredDetail =>
      item.settled.isNotEmpty ||
      item.mySide.isNotEmpty ||
      item.elsewhere.isNotEmpty ||
      item.next.isNotEmpty ||
      item.waiting != null ||
      item.blocker != null ||
      item.unknown != null;

  List<Widget> _detailSections(BuildContext context) {
    final seen = <String>{};
    List<String> unique(Iterable<String> values) => [
      for (final value in values)
        if (value.trim().isNotEmpty &&
            !_ongoingRedundant(value, item) &&
            seen.add(_ongoingKey(value)))
          value.trim(),
    ];

    seen
      ..add(_ongoingKey(item.title))
      ..add(_ongoingKey(item.synthesis));
    final sections = <Widget>[];

    // Settled — what's already done
    final settledValues = unique(item.settled);
    if (settledValues.isNotEmpty) {
      sections.add(
        _DimensionSection(title: 'Déjà réglé', values: settledValues),
      );
    }

    // My side — explicit action from me
    final mySideValues = unique(item.mySide);
    if (mySideValues.isNotEmpty) {
      sections.add(
        _DimensionSection(
          title: 'De votre côté',
          values: mySideValues,
          emphasis: true,
        ),
      );
    }

    // Elsewhere — things moving on the other side
    final elsewhereValues = unique(item.elsewhere);
    if (elsewhereValues.isNotEmpty) {
      sections.add(
        _DimensionSection(title: 'Ailleurs', values: elsewhereValues),
      );
    }

    // Next — what follows
    final nextValues = unique(item.next);
    if (nextValues.isNotEmpty) {
      sections.add(_DimensionSection(title: 'Ensuite', values: nextValues));
    }

    // Waiting — hourglass row
    if (item.waiting != null) {
      final waitingText = unique([item.waiting!]);
      if (waitingText.isNotEmpty) {
        sections.add(
          Padding(
            padding: const EdgeInsets.only(top: MakoloSpacing.lg),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  Icons.hourglass_top_outlined,
                  size: 18,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
                const SizedBox(width: MakoloSpacing.sm),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'En attente',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: MakoloSpacing.xs),
                      Text(waitingText.first),
                    ],
                  ),
                ),
              ],
            ),
          ),
        );
      }
    }

    // Blocker — attention block with warning styling
    if (item.blocker != null) {
      final blockerText = unique([item.blocker!]);
      if (blockerText.isNotEmpty) {
        sections.add(
          Padding(
            padding: const EdgeInsets.only(top: MakoloSpacing.lg),
            child: MakoloAttentionBlock(
              title: 'Ce qui bloque',
              body: blockerText.first,
              icon: Icons.block_outlined,
            ),
          ),
        );
      }
    }

    // Unknown — to verify
    if (item.unknown != null) {
      final unknownText = unique([item.unknown!]);
      if (unknownText.isNotEmpty) {
        sections.add(
          _DimensionSection(title: 'À vérifier', values: unknownText),
        );
      }
    }

    return sections;
  }

  List<MakoloMetadataItem> _humanMetadata() {
    final metadata = <MakoloMetadataItem>[];
    final start = MakoloHumanization.tryParseInstant(item.timing['start_at']);
    if (start != null) {
      metadata.add(
        MakoloMetadataItem(
          MakoloHumanization.formatDateTime(start, now: DateTime.now()),
          icon: Icons.schedule_outlined,
        ),
      );
    }

    final place = [
      item.place['name'],
      item.place['locality'],
    ].whereType<String>().where((value) => value.trim().isNotEmpty).toSet();
    if (place.isNotEmpty) {
      metadata.add(
        MakoloMetadataItem(place.join(' · '), icon: Icons.place_outlined),
      );
    }
    return metadata;
  }

  @override
  Widget build(BuildContext context) {
    final showBack =
        MediaQuery.sizeOf(context).width < MakoloLayout.ongoingSplitMinWidth;
    final metadata = _humanMetadata();
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.lg),
      child: MakoloFocusPane(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (showBack)
              TextButton.icon(
                onPressed: onBack,
                icon: const Icon(Icons.arrow_back),
                label: const Text('En cours'),
              ),
            Text(item.title, style: Theme.of(context).textTheme.headlineMedium),
            if (!_hasStructuredDetail) ...[
              const SizedBox(height: MakoloSpacing.sm),
              Text(
                item.synthesis,
                style: Theme.of(context).textTheme.bodyLarge,
              ),
            ],
            ..._detailSections(context),
            if (metadata.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: MakoloSpacing.lg),
                child: MakoloMetadata(items: metadata),
              ),
          ],
        ),
      ),
    );
  }
}

class _DimensionSection extends StatelessWidget {
  const _DimensionSection({
    required this.title,
    required this.values,
    this.emphasis = false,
  });
  final String title;
  final List<String> values;
  final bool emphasis;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: MakoloSpacing.lg),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
            color: emphasis ? Theme.of(context).colorScheme.primary : null,
          ),
        ),
        const SizedBox(height: MakoloSpacing.sm),
        for (final value in values) ...[
          Text(value, style: Theme.of(context).textTheme.bodyLarge),
          const SizedBox(height: MakoloSpacing.xs),
        ],
      ],
    ),
  );
}
