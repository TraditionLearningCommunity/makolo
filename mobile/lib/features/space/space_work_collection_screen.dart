import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../design/behavior_states.dart';
import '../../network/api_error.dart';
import '../../presentation/contracts/space_presentation.dart';
import 'space_work_surface.dart';

/// An ephemeral continuation of the existing work projection. Every page is
/// authorized again; it never replaces the synced root snapshot.
class SpaceWorkCollectionScreen extends StatefulWidget {
  const SpaceWorkCollectionScreen({
    super.key,
    required this.runtime,
    required this.actor,
    required this.section,
  });
  final AppRuntime runtime;
  final SpaceActorContext actor;
  final String section;
  @override
  State<SpaceWorkCollectionScreen> createState() =>
      _SpaceWorkCollectionScreenState();
}

class _SpaceWorkCollectionScreenState extends State<SpaceWorkCollectionScreen> {
  Map<String, dynamic>? payload;
  bool loading = false;
  bool denied = false;
  bool pageFailed = false;
  int version = 0;
  int nextOffset = 0;
  bool get actorValid => widget.runtime.actorContext?.value == widget.actor;

  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(onActorChanged);
    unawaited(_bootstrap());
  }

  @override
  void dispose() {
    version++;
    widget.runtime.actorContext?.removeListener(onActorChanged);
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant SpaceWorkCollectionScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime.actorContext != widget.runtime.actorContext) {
      oldWidget.runtime.actorContext?.removeListener(onActorChanged);
      widget.runtime.actorContext?.addListener(onActorChanged);
    }
    if (oldWidget.runtime != widget.runtime ||
        oldWidget.actor != widget.actor ||
        oldWidget.section != widget.section) {
      onActorChanged();
    }
  }

  void onActorChanged() {
    version++;
    if (!mounted) return;
    setState(() {
      payload = null;
      nextOffset = 0;
      loading = false;
      denied = false;
      pageFailed = false;
    });
    if (actorValid) unawaited(_bootstrap());
  }

  /// Reuse the owner-validated Space Work snapshot already acquired by the
  /// shell. A collection page is only a continuation; it does not own a
  /// separate persistent copy or create an independent offline cache.
  Future<void> _bootstrap() async {
    final revision = ++version;
    final repository = widget.runtime.space;
    final store = widget.runtime.store;
    final actor = widget.actor;
    if (repository != null && store != null && actorValid) {
      try {
        final source = repository.workSource(actor.space, actor.perspective);
        final state = await repository.readSource(source);
        final rejected =
            state.invalidated &&
            const {
              'permission_denied',
              'not_found',
            }.contains(state.lastErrorCode);
        if (!rejected) {
          final projection = await store.readProjection(
            source.projectionKind,
            resourceKey: source.resourceKey,
          );
          final expiry = projection?.expiresAt?.toUtc();
          final value = projection?.payload;
          final space = spaceMap(value?['space']);
          final sections = spaceMap(value?['sections']);
          final section = spaceMap(sections?[widget.section]);
          if (projection != null &&
              (expiry == null || DateTime.now().toUtc().isBefore(expiry)) &&
              space?['id'] == actor.space.id &&
              value?['responsibility'] == (actor.perspective.id ?? 'all') &&
              section?['items'] is List &&
              mounted &&
              revision == version &&
              actorValid) {
            setState(() {
              payload = {
                ...value!,
                'sections': {widget.section: section},
              };
              // A root snapshot is not a paginated continuation. Start at
              // owner offset zero so the server can reconcile membership.
              nextOffset = 0;
            });
          }
        }
      } on Object {
        // Unknown or withdrawn owner knowledge is never fabricated locally.
      }
    }
    if (mounted && revision == version && actorValid) {
      await loadPage();
    }
  }

  Future<void> loadPage() async {
    if (loading || !actorValid) return;
    final currentVersion = ++version;
    final offset = nextOffset;
    setState(() {
      loading = true;
      pageFailed = false;
    });
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('Owner API unavailable');
      final actor = widget.actor;
      final path = Uri(
        path:
            'api/v1/organizations/workspaces/${Uri.encodeComponent(actor.space.slug)}/work/',
        queryParameters: {
          'section': widget.section,
          'offset': '$offset',
          if (!actor.perspective.isAll) 'responsibility': actor.perspective.id!,
        },
      ).toString();
      final data = (await api.get(path)).jsonObject();
      if (!mounted || currentVersion != version || !actorValid) return;
      final sections = spaceMap(data['sections']);
      final section = spaceMap(sections?[widget.section]);
      final page = spaceMap(data['page']);
      if (spaceMap(data['space'])?['id'] != actor.space.id ||
          data['responsibility'] != (actor.perspective.id ?? 'all') ||
          section == null ||
          section['items'] is! List ||
          page?['offset'] != offset ||
          page?['limit'] is! int) {
        throw const FormatException(
          'Work page does not match actor or section',
        );
      }
      final previous = spaceMap(
        spaceMap(payload?['sections'])?[widget.section],
      );
      final items = <String, Map<String, dynamic>>{};
      for (final row in [
        ...?previous?['items'] as List?,
        ...section['items'] as List,
      ]) {
        final item = spaceMap(row);
        final source = spaceMap(item?['source']);
        if (item != null &&
            source?['kind'] is String &&
            source?['id'] is String) {
          items['${source!['kind']}:${source['id']}'] = item;
        }
      }
      setState(() {
        payload = {
          ...data,
          'sections': {
            widget.section: {...section, 'items': items.values.toList()},
          },
        };
        nextOffset = offset + (page!['limit'] as int);
        denied = false;
      });
    } on Object catch (error) {
      if (!mounted || currentVersion != version) return;
      setState(() {
        pageFailed = true;
        denied =
            error is MakoloApiError &&
            const {401, 403, 404}.contains(error.statusCode);
        if (denied) payload = null;
      });
    } finally {
      if (mounted && currentVersion == version) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(spaceText(payload?['primary_business_label']) ?? 'Métier'),
    ),
    body: !actorValid || denied
        ? const MakoloEmptyState(
            title: 'Cette collection n’est plus accessible dans le contexte actuel.',
            icon: Icons.lock_outline,
          )
        : Column(
            children: [
              if (loading) const LinearProgressIndicator(),
              Expanded(
                child: payload == null
                    ? loading
                          ? const Center(child: CircularProgressIndicator())
                          : MakoloErrorState(
                              message: 'Impossible d’afficher la liste.',
                              onRetry: loadPage,
                            )
                    : SpaceWorkSurface(
                        payload: payload!,
                        mediaBaseUri: widget.runtime.api?.baseUri,
                        onLoadMore: (_) {
                          if (!loading && !pageFailed) {
                            unawaited(loadPage());
                          }
                        },
                      ),
              ),
              if (pageFailed && payload != null && !denied)
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: MakoloActionButton(
                    label: 'Réessayer la liste',
                    onPressed: loadPage,
                    appearance: MakoloActionAppearance.quiet,
                  ),
                ),
            ],
          ),
  );
}
