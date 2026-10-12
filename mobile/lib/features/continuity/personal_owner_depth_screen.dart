import 'package:flutter/material.dart';

import '../../app/runtime/app_runtime.dart';
import '../../app/runtime/actor_context.dart';
import '../../design/makolo_patterns.dart';
import '../../presentation/contracts/space_presentation.dart';

/// Directly consults the canonical personal owner projection before display.
class PersonalOwnerDepthScreen extends StatefulWidget {
  const PersonalOwnerDepthScreen({
    super.key,
    required this.runtime,
    required this.kind,
    required this.id,
  });

  final AppRuntime runtime;
  final String kind;
  final String id;

  @override
  State<PersonalOwnerDepthScreen> createState() =>
      _PersonalOwnerDepthScreenState();
}

class _PersonalOwnerDepthScreenState extends State<PersonalOwnerDepthScreen> {
  late Future<Map<String, dynamic>> _detail;
  bool get _actorValid =>
      widget.runtime.actorContext?.value is! SpaceActorContext;

  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(_onActorChanged);
    _detail = _load();
  }

  void _onActorChanged() {
    if (!mounted) return;
    setState(
      () => _detail = _actorValid
          ? _load()
          : Future.value(const <String, dynamic>{}),
    );
  }

  @override
  void dispose() {
    widget.runtime.actorContext?.removeListener(_onActorChanged);
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant PersonalOwnerDepthScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime.actorContext != widget.runtime.actorContext) {
      oldWidget.runtime.actorContext?.removeListener(_onActorChanged);
      widget.runtime.actorContext?.addListener(_onActorChanged);
    }
    if (oldWidget.runtime != widget.runtime ||
        oldWidget.id != widget.id ||
        oldWidget.kind != widget.kind) {
      _detail = _load();
    }
  }

  Future<Map<String, dynamic>> _load() async {
    if (!_actorValid) return const {};
    final runtime = widget.runtime;
    final api = widget.runtime.api;
    if (api == null) {
      throw StateError('Owner service unavailable');
    }
    final segment = switch (widget.kind) {
      'personal_asset' => 'resources/${Uri.encodeComponent(widget.id)}/',
      'group' => 'collectives/groups/${Uri.encodeComponent(widget.id)}/',
      'commerce_order' => 'orders/${Uri.encodeComponent(widget.id)}/',
      _ => throw const FormatException('Unknown owner kind'),
    };
    final response = await api.get('api/v1/me/$segment');
    if (!_actorValid || runtime != widget.runtime) {
      throw StateError('Owner context changed');
    }
    final envelope = response.jsonObject();
    final raw = envelope['data'];
    if (raw is! Map) throw const FormatException('Invalid owner response');
    final payload = Map<String, dynamic>.from(raw);
    if (payload['id'] != widget.id || payload['kind'] != widget.kind) {
      throw const FormatException('Wrong owner identity');
    }
    return payload;
  }

  @override
  Widget build(BuildContext context) {
    final document = widget.kind == 'personal_asset';
    final order = widget.kind == 'commerce_order';
    return Scaffold(
      appBar: AppBar(
        title: Text(
          document
              ? 'Mon document'
              : order
              ? 'Ma commande'
              : 'Mon groupe',
        ),
      ),
      body: !_actorValid
          ? const Center(
              child: Text(
                'Revenez à votre contexte personnel pour cette commande.',
              ),
            )
          : FutureBuilder<Map<String, dynamic>>(
              future: _detail,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (!snapshot.hasData) {
                  return Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Text(
                          'Cette information n’est pas disponible '
                          'avec votre accès actuel.',
                        ),
                        TextButton(
                          onPressed: () => setState(() => _detail = _load()),
                          child: const Text('Réessayer'),
                        ),
                      ],
                    ),
                  );
                }
                final data = snapshot.data!;
                final title = document || order ? data['title'] : data['name'];
                final details = <String>[
                  if (document)
                    data['asset_kind_label']?.toString() ?? 'Document',
                  if (!document && data['description'] is String)
                    data['description'] as String,
                  if (data['status'] is String)
                    spaceStateLabel(data['status'] as String),
                  if (order && data['activity'] is Map)
                    (data['activity'] as Map)['title']?.toString() ?? '',
                ];
                return ListView(
                  padding: const EdgeInsets.all(24),
                  children: [
                    MakoloDetailHeader(title: title?.toString() ?? 'Élément'),
                    const SizedBox(height: 16),
                    for (final detail in details)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: Text(detail),
                      ),
                    if (document) ...[
                      const SizedBox(height: 20),
                      const Text(
                        'Un document conservé ne satisfait pas '
                        'automatiquement une exigence.',
                      ),
                    ],
                    if (!document && data['members'] is Map) ...[
                      const SizedBox(height: 16),
                      Text(
                        'Membres actifs : '
                        '${(data['members'] as Map)['active_count'] ?? 'Non précisé'}',
                      ),
                    ],
                  ],
                );
              },
            ),
    );
  }
}
