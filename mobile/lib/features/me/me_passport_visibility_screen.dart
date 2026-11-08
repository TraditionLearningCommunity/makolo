import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import '../../network/makolo_api_client.dart';
import '../../sync/projection_contract.dart';

/// Owner-only presentation privacy; never edits source-domain facts.
class MePassportVisibilityScreen extends StatefulWidget {
  const MePassportVisibilityScreen({super.key, required this.api});
  final MakoloApiClient api;

  @override
  State<MePassportVisibilityScreen> createState() => _VisibilityState();
}

class _VisibilityState extends State<MePassportVisibilityScreen> {
  Map<String, dynamic>? _data;
  bool _loading = true;

  static Map<String, dynamic> _map(Object? value) => value is Map
      ? value.map((key, item) => MapEntry(key.toString(), item))
      : <String, dynamic>{};
  static List<Map<String, dynamic>> _rows(Object? value) => value is List
      ? value.whereType<Map>().map(_map).toList()
      : <Map<String, dynamic>>[];

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    try {
      final response = await widget.api.get(
        'api/v1/me/passport/visibility/?compact=1',
      );
      final data = ProjectionEnvelope.parse(
        response.jsonObject(),
        expectedProjection: 'personal.me.passport.visibility',
      ).data;
      if (mounted) {
        setState(() {
          _data = data;
          _loading = false;
        });
      }
    } on Object {
      if (mounted) {
        setState(() {
          _data = null;
          _loading = false;
        });
      }
    }
  }

  Future<void> _edit(
    String kind,
    String id,
    String label,
    Map<String, dynamic> setting,
  ) async {
    final collectives = _map(_data?['collectives']);
    final choices = <Map<String, dynamic>>[
      {'kind': 'public', 'label': 'Tout le monde'},
      {'kind': 'my_collectives', 'label': 'Mes collectifs, y compris futurs'},
      for (final family in ['spaces', 'teams', 'groups'])
        for (final row in _rows(collectives[family]))
          {'kind': row['kind'], 'id': row['id'], 'label': row['label']},
    ];
    String token(Map<String, dynamic> item) =>
        '${item['kind']}:${item['id']?.toString() ?? ''}';
    final selected = _rows(setting['audiences']).map(token).toSet();
    for (final row in _rows(setting['audiences'])) {
      if (row['kind'] == 'selected_profile' && row['id'] != null) {
        choices.add({
          'kind': 'selected_profile',
          'id': row['id'],
          'label': row['label'] ?? 'Personne choisie',
        });
      }
    }
    final searchInput = TextEditingController();
    var candidates = <Map<String, dynamic>>[];
    var working = false;
    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (sheet) => StatefulBuilder(
        builder: (sheet, redraw) {
          Future<void> search() async {
            if (searchInput.text.trim().length < 2) return;
            try {
              final url = Uri(
                path: 'api/v1/sharing/recipients/',
                queryParameters: {'q': searchInput.text.trim()},
              ).toString();
              final response = await widget.api.get(url);
              if (sheet.mounted) {
                redraw(() {
                  candidates = _rows(response.jsonObject()['results']);
                });
              }
            } on Object {
              if (sheet.mounted) redraw(() => candidates = []);
            }
          }

          Future<void> save() async {
            redraw(() => working = true);
            try {
              final audiences = selected.map((key) {
                final index = key.indexOf(':');
                final target = key.substring(index + 1);
                return <String, dynamic>{
                  'kind': key.substring(0, index),
                  if (target.isNotEmpty) 'id': target,
                };
              }).toList();
              await widget.api.put(
                'api/v1/me/passport/visibility/',
                body: {
                  'target_kind': kind,
                  if (kind == 'field') 'field_key': id,
                  if (kind != 'field') 'target_id': id,
                  'audiences': audiences,
                },
              );
              if (!sheet.mounted) return;
              Navigator.pop(sheet);
              await _refresh();
            } on Object {
              if (sheet.mounted) {
                redraw(() => working = false);
                ScaffoldMessenger.of(sheet).showSnackBar(
                  const SnackBar(content: Text('Enregistrement impossible.')),
                );
              }
            }
          }

          return SafeArea(
            child: Padding(
              padding: EdgeInsets.only(
                left: 16,
                right: 16,
                bottom: MediaQuery.viewInsetsOf(sheet).bottom + 12,
              ),
              child: SizedBox(
                height: MediaQuery.sizeOf(sheet).height * .49,
                child: Column(
                  children: [
                    Text(label, style: Theme.of(sheet).textTheme.titleLarge),

                    Expanded(
                      child: ListView(
                        children: [
                          ListTile(
                            dense: true,
                            leading: const Icon(Icons.public_outlined),
                            title: const Text('Tout le monde'),
                            subtitle: const Text(
                              'Cette information est publique',
                            ),
                            trailing: selected.contains('public:')
                                ? const Icon(Icons.check_circle)
                                : null,
                            onTap: working
                                ? null
                                : () => redraw(() {
                                    selected
                                      ..clear()
                                      ..add('public:');
                                  }),
                          ),
                          ListTile(
                            dense: true,
                            leading: const Icon(Icons.lock_outline),
                            title: const Text('Moi uniquement'),
                            subtitle: const Text('Aucune audience autorisée'),
                            trailing: selected.isEmpty
                                ? const Icon(Icons.check_circle)
                                : null,
                            onTap: working
                                ? null
                                : () => redraw(selected.clear),
                          ),
                          ExpansionTile(
                            tilePadding: EdgeInsets.zero,
                            title: const Text(
                              'Choisir des personnes ou collectifs',
                            ),
                            subtitle: const Text('Options avancées'),
                            children: [
                              for (final option in choices)
                                if (option['kind'] != 'public')
                                  CheckboxListTile(
                                    dense: true,
                                    title: Text(
                                      option['label']?.toString() ?? '',
                                    ),
                                    value: selected.contains(token(option)),
                                    onChanged: working
                                        ? null
                                        : (value) => redraw(() {
                                            final key = token(option);
                                            if (value == true) {
                                              selected.remove('public:');
                                              selected.add(key);
                                            } else {
                                              selected.remove(key);
                                            }
                                          }),
                                  ),
                              TextField(
                                controller: searchInput,
                                decoration: InputDecoration(
                                  labelText: 'Rechercher une personne Makolo',
                                  suffixIcon: MakoloIconActionButton(
                                    tooltip: 'Rechercher une personne Makolo',
                                    onPressed: working ? null : search,
                                    icon: Icons.search,
                                  ),
                                ),
                                onSubmitted: (_) => search(),
                              ),
                              for (final person in candidates)
                                ListTile(
                                  title: Text(
                                    person['name']?.toString() ?? 'Profil',
                                  ),
                                  subtitle: Text(
                                    '@${person['username']?.toString() ?? ''}',
                                  ),
                                  onTap: () => redraw(() {
                                    if (person['id'] == null) return;
                                    final item = {
                                      'kind': 'selected_profile',
                                      'id': person['id'],
                                      'label': person['name'],
                                    };
                                    if (!choices.any(
                                      (row) => token(row) == token(item),
                                    )) {
                                      choices.add(item);
                                    }
                                    selected.remove('public:');
                                    selected.add(token(item));
                                    candidates = [];
                                  }),
                                ),
                            ],
                          ),
                        ],
                      ),
                    ),
                    Row(
                      children: [
                        MakoloActionButton(
                          label: 'Annuler',
                          onPressed: working
                              ? null
                              : () => Navigator.pop(sheet),
                          appearance: MakoloActionAppearance.quiet,
                        ),
                        const Spacer(),
                        MakoloActionButton(
                          label: working ? 'Enregistrement…' : 'Enregistrer',
                          onPressed: working ? null : save,
                          appearance: MakoloActionAppearance.primary,
                          busy: working,
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
    searchInput.dispose();
  }

  Widget _entry(
    String title,
    String kind,
    String id,
    Map<String, dynamic> rule,
  ) {
    final audiences = _rows(rule['audiences']);
    final subtitle = audiences.isEmpty
        ? 'Moi uniquement'
        : audiences
              .map((row) {
                if (row['kind'] == 'public') return 'Public';
                if (row['kind'] == 'my_collectives') return 'Mes collectifs';
                return row['label']?.toString() ?? 'Audience choisie';
              })
              .join(' · ');
    return ListTile(
      title: Text(title),
      subtitle: Text(subtitle, maxLines: 2),
      trailing: const Icon(Icons.tune_outlined),
      onTap: () => _edit(kind, id, title, rule),
    );
  }

  static String _label(String key) =>
      const {
        'name': 'Nom',
        'avatar': 'Photo',
        'bio': 'À propos',
        'profession': 'Profession',
        'city': 'Ville',
        'country': 'Pays',
        'company_name': 'Entreprise',
        'organization_name': 'Organisation',
        'website': 'Site web',
        'linkedin_url': 'LinkedIn',
        'facebook_url': 'Facebook',
        'instagram_url': 'Instagram',
        'tiktok_url': 'TikTok',
        'x_url': 'X',
        'youtube_url': 'YouTube',
      }[key] ??
      key;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Confidentialité du Passeport')),
    body: _loading
        ? const Center(child: CircularProgressIndicator())
        : _data == null
        ? Center(
            child: MakoloActionButton(
              label: 'Réessayer avec une connexion',
              appearance: MakoloActionAppearance.quiet,
              onPressed: () {
                setState(() => _loading = true);
                _refresh();
              },
            ),
          )
        : ListView(
            children: [
              const ListTile(title: Text('Informations du Profil')),
              for (final entry in _map(_data!['fields']).entries)
                if (_map(entry.value)['has_value'] != false)
                  _entry(
                    _label(entry.key),
                    'field',
                    entry.key,
                    _map(entry.value),
                  ),
              if (_map(_data!['fields']).entries
                  .any((entry) => _map(entry.value)['has_value'] == false))
                ExpansionTile(
                  title: const Text('Autres réglages'),
                  children: [
                    for (final entry in _map(_data!['fields']).entries)
                      if (_map(entry.value)['has_value'] == false)
                        _entry(
                          _label(entry.key),
                          'field',
                          entry.key,
                          _map(entry.value),
                        ),
                  ],
                ),
              const Divider(),
              _entry(
                'Centres d’intérêt',
                'field',
                'interests',
                _map(_map(_data!['collections'])['interests']),
              ),
              _entry(
                'Ouvert à',
                'field',
                'open_to',
                _map(_map(_data!['collections'])['open_to']),
              ),
            ],
          ),
  );
}
