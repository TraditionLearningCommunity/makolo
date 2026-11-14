import 'dart:async';

import 'package:flutter/material.dart';

import '../../network/makolo_api_client.dart';

/// Project invitation composition. An invitation is never an active Mandate.
class ProjectInviteSheet extends StatefulWidget {
  const ProjectInviteSheet({
    super.key,
    required this.api,
    required this.projectId,
    required this.spaceSlug,
    required this.roles,
    required this.candidates,
  });

  final MakoloApiClient api;
  final String projectId;
  final String? spaceSlug;
  final List<Map<String, dynamic>> roles;
  final List<Map<String, dynamic>> candidates;

  @override
  State<ProjectInviteSheet> createState() => _ProjectInviteSheetState();
}

class _ProjectInviteSheetState extends State<ProjectInviteSheet> {
  final _query = TextEditingController();
  Timer? _debounce;
  int _revision = 0;
  String? _selectedId;
  String _role = 'project-viewer';
  List<Map<String, dynamic>> _results = [];
  bool _searching = false;
  bool _sending = false;
  String? _error;

  String get _scope => widget.spaceSlug == null
      ? ''
      : '?context=space&space=${Uri.encodeQueryComponent(widget.spaceSlug!)}';

  @override
  void dispose() {
    _debounce?.cancel();
    _query.dispose();
    super.dispose();
  }

  static String _label(String role) => switch (role) {
    'project-viewer' => 'Lecteur',
    'project-manager' => 'Éditeur',
    'project-admin' => 'Administrateur',
    _ => 'Accès',
  };

  static String _explain(String role) => switch (role) {
    'project-viewer' => 'Consulter ce Projet',
    'project-manager' => 'Modifier et organiser le Projet',
    'project-admin' => 'Gérer le Projet et ses accès',
    _ => '',
  };

  static IconData _icon(String role) => switch (role) {
    'project-viewer' => Icons.visibility_outlined,
    'project-manager' => Icons.edit_outlined,
    'project-admin' => Icons.admin_panel_settings_outlined,
    _ => Icons.person_outline,
  };

  void _onQuery(String input) {
    final revision = ++_revision;
    _debounce?.cancel();
    setState(() {
      _selectedId = null;
      _searching = false;
      _error = null;
      _results = [];
    });
    final query = input.trim();
    if (query.length < 2) return;
    _debounce = Timer(const Duration(milliseconds: 320), () async {
      if (!mounted || revision != _revision) return;
      setState(() => _searching = true);
      try {
        final path =
            'api/v1/objectives/projects/${widget.projectId}/people/search/'
            '?q=${Uri.encodeQueryComponent(query)}'
            '${_scope.isEmpty ? '' : '&${_scope.substring(1)}'}';
        final result = (await widget.api.get(path)).jsonObject();
        final rows = result['results'];
        if (!mounted || revision != _revision) return;
        setState(() {
          _results = rows is List
              ? rows
                    .whereType<Map>()
                    .map((m) => m.map((k, v) => MapEntry(k.toString(), v)))
                    .toList()
              : [];
        });
      } on Object {
        // A failed automatic lookup does not block exact-identifier entry.
        // Do not show a network-error cascade while typing.
      } finally {
        if (mounted && revision == _revision) {
          setState(() => _searching = false);
        }
      }
    });
  }

  Future<void> _submit() async {
    final value = _query.text.trim();
    if (_sending || (_selectedId == null && value.isEmpty)) return;
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      final input = _selectedId != null
          ? <String, dynamic>{'profile_id': _selectedId}
          : <String, dynamic>{
              'identity': value.startsWith('@') ? value.substring(1) : value,
            };
      await widget.api.post(
        'api/v1/objectives/projects/${widget.projectId}/invitations/$_scope',
        body: {...input, 'role_code': _role},
      );
      if (mounted) Navigator.of(context).pop(true);
    } on Object {
      if (mounted) {
        setState(
          () => _error =
              'Invitation non envoyée. Vérifiez le compte choisi ou réessayez.',
        );
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final roleCodes = widget.roles.map((r) => r['code']?.toString()).toSet();
    final offered = [
      'project-viewer',
      'project-manager',
      'project-admin',
    ].where(roleCodes.contains).toList();
    final local = widget.candidates
        .where((row) {
          final q = _query.text.trim().toLowerCase();
          return q.length >= 2 &&
              (row['label']?.toString().toLowerCase().contains(q) ?? false);
        })
        .take(5);
    final suggestions = [..._results, if (_results.isEmpty) ...local];
    return SafeArea(
      top: false,
      child: Padding(
        padding: EdgeInsets.fromLTRB(
          18,
          10,
          18,
          MediaQuery.viewInsetsOf(context).bottom + 18,
        ),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'Inviter à collaborer',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _query,
                autofocus: true,
                onChanged: _onQuery,
                decoration: InputDecoration(
                  prefixIcon: const Icon(Icons.search_rounded),
                  hintText: 'Nom, @identifiant ou e-mail',
                  filled: true,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                  suffixIcon: _searching
                      ? const Padding(
                          padding: EdgeInsets.all(12),
                          child: SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                        )
                      : null,
                ),
                textInputAction: TextInputAction.search,
              ),
              if (suggestions.isNotEmpty) ...[
                const SizedBox(height: 5),
                for (final person in suggestions.take(6))
                  ListTile(
                    dense: true,
                    contentPadding: const EdgeInsets.symmetric(horizontal: 5),
                    leading: CircleAvatar(
                      child: const Icon(Icons.person_outline_rounded),
                    ),
                    title: Text(
                      person['name']?.toString() ??
                          person['label']?.toString() ??
                          '',
                    ),
                    subtitle: Text(
                      [
                        if (person['username'] != null)
                          '@${person['username']}',
                        if (person['email'] != null) person['email'].toString(),
                      ].join(' · '),
                    ),
                    trailing: _selectedId == (person['id']?.toString())
                        ? Icon(Icons.check_circle, color: scheme.primary)
                        : null,
                    onTap: () => setState(() {
                      _selectedId = person['id']?.toString();
                      _query.text =
                          person['name']?.toString() ??
                          person['label']?.toString() ??
                          '';
                      _query.selection = TextSelection.collapsed(
                        offset: _query.text.length,
                      );
                      _results = [];
                      _debounce?.cancel();
                      _revision++;
                    }),
                  ),
              ],
              const SizedBox(height: 12),
              Text(
                'Accès proposé',
                style: Theme.of(context).textTheme.titleSmall,
              ),
              const SizedBox(height: 7),
              for (final code in offered)
                Padding(
                  padding: const EdgeInsets.only(bottom: 5),
                  child: Material(
                    borderRadius: BorderRadius.circular(13),
                    color: code == _role
                        ? scheme.primaryContainer.withValues(alpha: .45)
                        : scheme.surfaceContainerLow,
                    child: InkWell(
                      borderRadius: BorderRadius.circular(13),
                      onTap: () => setState(() => _role = code),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 11,
                        ),
                        child: Row(
                          children: [
                            Icon(
                              _icon(code),
                              size: 21,
                              color: code == _role
                                  ? scheme.primary
                                  : scheme.onSurfaceVariant,
                            ),
                            const SizedBox(width: 11),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    _label(code),
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                  Text(
                                    _explain(code),
                                    style: Theme.of(context)
                                        .textTheme
                                        .bodySmall,
                                  ),
                                ],
                              ),
                            ),
                            if (code == _role)
                              Icon(
                                Icons.check_circle_rounded,
                                color: scheme.primary,
                                size: 20,
                              ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.only(top: 5),
                  child: Text(_error!, style: TextStyle(color: scheme.error)),
                ),
              const SizedBox(height: 10),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: _sending ? null : () => Navigator.pop(context),
                    child: const Text('Annuler'),
                  ),
                  const SizedBox(width: 7),
                  FilledButton.icon(
                    onPressed: _sending ? null : _submit,
                    icon: const Icon(Icons.send_outlined, size: 19),
                    label: Text(_sending ? 'Envoi…' : 'Inviter'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
