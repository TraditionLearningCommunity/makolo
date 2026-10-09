import 'package:flutter/material.dart';

import '../../app/runtime/app_runtime.dart';

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

  @override
  void initState() {
    super.initState();
    _detail = _load();
  }

  @override
  void didUpdateWidget(covariant PersonalOwnerDepthScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime != widget.runtime ||
        oldWidget.id != widget.id ||
        oldWidget.kind != widget.kind) {
      _detail = _load();
    }
  }

  Future<Map<String, dynamic>> _load() async {
    final api = widget.runtime.api;
    if (api == null) {
      throw StateError('Owner service unavailable');
    }
    final segment = widget.kind == 'personal_asset'
        ? 'resources/${Uri.encodeComponent(widget.id)}/'
        : 'collectives/groups/${Uri.encodeComponent(widget.id)}/';
    final response = await api.get('api/v1/me/$segment');
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
    return Scaffold(
      appBar: AppBar(title: Text(document ? 'Mon document' : 'Mon groupe')),
      body: FutureBuilder<Map<String, dynamic>>(
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
          final title = document ? data['title'] : data['name'];
          final details = <String>[
            if (document)
              data['asset_kind_label']?.toString() ?? 'Document',
            if (!document && data['description'] is String)
              data['description'] as String,
            if (data['status'] is String) data['status'] as String,
          ];
          return ListView(
            padding: const EdgeInsets.all(24),
            children: [
              Text(
                title?.toString() ?? 'Élément',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
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
