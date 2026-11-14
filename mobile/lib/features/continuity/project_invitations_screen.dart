import 'package:flutter/material.dart';

import '../../network/makolo_api_client.dart';

/// Personal inbox for Project invitations. An invitation does not grant any
/// Project, Dossier or Conversation access until explicitly accepted.
class ProjectInvitationsScreen extends StatefulWidget {
  const ProjectInvitationsScreen({
    super.key,
    required this.api,
    required this.onOpenProject,
  });

  final MakoloApiClient api;
  final ValueChanged<String> onOpenProject;

  @override
  State<ProjectInvitationsScreen> createState() =>
      _ProjectInvitationsScreenState();
}

class _ProjectInvitationsScreenState extends State<ProjectInvitationsScreen> {
  List<Map<String, dynamic>>? _invitations;
  bool _loading = false;
  String? _error;
  final Set<String> _pending = {};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (_loading) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final response = (await widget.api.get(
        'api/v1/objectives/projects/invitations/',
      )).jsonObject();
      final rows = response['results'];
      if (!mounted) return;
      setState(() {
        _invitations = rows is List
            ? rows
                  .whereType<Map>()
                  .map(
                    (row) => row.map(
                      (key, value) => MapEntry(key.toString(), value),
                    ),
                  )
                  .toList()
            : null;
      });
    } on Object {
      if (mounted) setState(() => _error = 'Invitations indisponibles.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _respond(Map<String, dynamic> row, bool accept) async {
    final id = row['id']?.toString();
    if (id == null || _pending.contains(id)) return;
    setState(() => _pending.add(id));
    try {
      final response = (await widget.api.post(
        'api/v1/objectives/projects/invitations/$id/respond/',
        body: {'action': accept ? 'accept' : 'decline'},
      )).jsonObject();
      if (!mounted) return;
      setState(
        () => _invitations?.removeWhere(
          (invitation) => invitation['id']?.toString() == id,
        ),
      );
      if (accept) {
        final projectId = response['project_id']?.toString();
        if (projectId != null && projectId.isNotEmpty) {
          widget.onOpenProject(projectId);
        }
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Réponse non confirmée. Réessayez.')),
        );
      }
    } finally {
      if (mounted) setState(() => _pending.remove(id));
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Invitations'),
        actions: [
          IconButton(
            tooltip: 'Actualiser les invitations',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: _invitations == null
          ? Center(
              child: _loading
                  ? const CircularProgressIndicator.adaptive()
                  : _error != null
                  ? TextButton.icon(
                      onPressed: _load,
                      icon: const Icon(Icons.refresh_rounded),
                      label: const Text('Réessayer'),
                    )
                  : const SizedBox.shrink(),
            )
          : _invitations!.isEmpty
          ? const Center(child: Text('Aucune invitation en attente.'))
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView.separated(
                padding: const EdgeInsets.symmetric(
                  vertical: 8,
                  horizontal: 16,
                ),
                itemCount: _invitations!.length,
                separatorBuilder: (_, _) => const Divider(height: 1),
                itemBuilder: (context, index) {
                  final row = _invitations![index];
                  final id = row['id']?.toString() ?? '';
                  final busy = _pending.contains(id);
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          row['project_title']?.toString() ?? 'Projet',
                          style: Theme.of(context).textTheme.titleMedium
                              ?.copyWith(fontWeight: FontWeight.w700),
                        ),
                        const SizedBox(height: 3),
                        Text(
                          '${row['invited_by'] ?? ''} · '
                          '${row['role'] ?? ''}',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        const SizedBox(height: 7),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.end,
                          children: [
                            TextButton(
                              onPressed: busy
                                  ? null
                                  : () => _respond(row, false),
                              child: const Text('Décliner'),
                            ),
                            const SizedBox(width: 7),
                            FilledButton(
                              onPressed: busy
                                  ? null
                                  : () => _respond(row, true),
                              child: const Text('Accepter'),
                            ),
                          ],
                        ),
                      ],
                    ),
                  );
                },
              ),
            ),
    );
  }
}
