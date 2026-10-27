import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../design/makolo_theme.dart';
import '../../network/makolo_api_client.dart';
import '../../sync/projection_contract.dart';

/// Native presentation of the same server-owned Passport variants as Web.
class MePassportScreen extends StatefulWidget {
  const MePassportScreen({super.key, required this.api});
  final MakoloApiClient api;
  @override
  State<MePassportScreen> createState() => _MePassportScreenState();
}

class _MePassportScreenState extends State<MePassportScreen> {
  String _variant = 'complete';
  String? _topic;
  Set<String> _sections = {'interests', 'open_to'};
  Set<String> _activities = {}, _proofs = {}, _credentials = {};
  Map<String, dynamic>? _full;
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() { super.initState(); _future = _load(); }

  Future<Map<String, dynamic>> _load() async {
    final params = <String, dynamic>{'variant': _variant};
    if (_variant == 'thematic' && _topic != null) params['topic'] = _topic;
    if (_variant == 'custom') {
      params['include'] = _sections.toList();
      params['activity'] = _activities.toList();
      params['proof'] = _proofs.toList();
      params['credential'] = _credentials.toList();
    }
    final url = Uri(path: 'api/v1/me/passport/', queryParameters: params).toString();
    final response = await widget.api.get(url);
    final data = ProjectionEnvelope.parse(
      response.jsonObject(), expectedProjection: 'personal.me.passport',
    ).data;
    if (_variant == 'complete') {
      _full = data;
      if (_activities.isEmpty && _proofs.isEmpty && _credentials.isEmpty) {
        _activities = _ids(data['activities']);
        _proofs = _ids(_map(data['established'])['proofs']);
        _credentials = _ids(_map(data['issued'])['credentials']);
      }
    }
    return data;
  }

  static Map<String, dynamic> _map(Object? raw) => raw is Map
      ? raw.map((key, value) => MapEntry(key.toString(), value))
      : <String, dynamic>{};
  static List<Map<String, dynamic>> _rows(Object? raw) => raw is List
      ? raw.whereType<Map>().map(_map).toList() : const [];
  static Set<String> _ids(Object? raw) => {
    for (final row in _rows(raw)) if (row['id'] != null) row['id'].toString(),
  };
  static String? _text(Object? raw) =>
      raw is String && raw.trim().isNotEmpty ? raw.trim() : null;

  void _select(String variant) {
    if (_variant == variant) return;
    if (variant == 'thematic' && _topic == null) {
      final options = _rows(_full?['topic_options']);
      if (options.isNotEmpty) _topic = options.first['code']?.toString();
    }
    setState(() { _variant = variant; _future = _load(); });
  }

  Future<void> _copyPublicLink(Map<String, dynamic> data) async {
    if (_map(data['projection'])['public_profile_enabled'] != true) return;
    final path = _text(_map(data['links'])['public_web']);
    if (path == null || !path.startsWith('/') || path.startsWith('//')) return;
    final uri = widget.api.baseUri.resolve(path);
    await Clipboard.setData(ClipboardData(text: uri.toString()));
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Lien public copié.')),
    );
  }

  void _toggle(Set<String> values, String id, bool enabled) {
    setState(() {
      if (enabled) { values.add(id); } else { values.remove(id); }
      _future = _load();
    });
  }

  Widget _options(Map<String, dynamic> data) {
    final source = _full ?? data;
    final topics = _rows(source['topic_options']);
    final theme = Theme.of(context);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(children: [
          for (final option in const [
            ('complete', 'Complet'), ('public', 'Public'),
            ('thematic', 'Thématique'), ('custom', 'Personnalisé'),
          ])
            Padding(
              padding: const EdgeInsets.only(right: 7),
              child: ChoiceChip(
                label: Text(option.$2),
                selected: _variant == option.$1,
                onSelected: (_) => _select(option.$1),
              ),
            ),
        ]),
      ),
      if (_variant == 'thematic') ...[
        const SizedBox(height: 10),
        if (topics.isEmpty)
          const Text('Aucun thème disponible.')
        else
          DropdownButtonFormField<String>(
            value: _topic,
            isExpanded: true,
            decoration: const InputDecoration(
              labelText: 'Thème', border: OutlineInputBorder(),
            ),
            items: [
              for (final topic in topics)
                if (topic['code'] != null)
                  DropdownMenuItem(
                    value: topic['code'].toString(),
                    child: Text(topic['label']?.toString() ?? ''),
                  ),
            ],
            onChanged: (code) => setState(() {
              _topic = code;
              _future = _load();
            }),
          ),
      ],
      if (_variant == 'custom') ...[
        const SizedBox(height: 14),
        Text('À présenter', style: theme.textTheme.titleMedium),
        Wrap(spacing: 6, children: [
          for (final option in const [
            ('interests', 'Intérêts'), ('open_to', 'Ouvert à'),
          ])
            FilterChip(
              label: Text(option.$2),
              selected: _sections.contains(option.$1),
              onSelected: (v) => _toggle(_sections, option.$1, v),
            ),
        ]),
        _selection('Activités', _rows(source['activities']), _activities,
            (row) => _text(row['title'])),
        _selection('Faits établis',
            _rows(_map(source['established'])['proofs']), _proofs,
            (row) => _text(row['proof_type_label'])),
        _selection('Attestations',
            _rows(_map(source['issued'])['credentials']), _credentials,
            (row) => _text(row['title'])),
      ],
    ]);
  }

  Widget _selection(String heading, List<Map<String, dynamic>> rows,
      Set<String> selected, String? Function(Map<String, dynamic>) label) {
    if (rows.isEmpty) return const SizedBox.shrink();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const SizedBox(height: 10),
      Text(heading, style: Theme.of(context).textTheme.labelLarge),
      for (final row in rows)
        if (row['id'] != null && label(row) != null)
          CheckboxListTile(
            dense: true, contentPadding: EdgeInsets.zero,
            title: Text(label(row)!),
            value: selected.contains(row['id'].toString()),
            onChanged: (enabled) => _toggle(
              selected, row['id'].toString(), enabled == true,
            ),
          ),
    ]);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Passeport Makolo')),
    body: FutureBuilder<Map<String, dynamic>>(
      future: _future,
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          if (snapshot.hasError) return Center(child: TextButton.icon(
            onPressed: () => setState(() => _future = _load()),
            icon: const Icon(Icons.refresh), label: const Text('Réessayer'),
          ));
          return const Center(child: CircularProgressIndicator.adaptive());
        }
        final data = snapshot.data!;
        return ListView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
          children: [
            _options(data),
            const SizedBox(height: 16),
            _PassportBody(data: data, baseUri: widget.api.baseUri),
            if (_map(data['projection'])['public_profile_enabled'] == true &&
                _text(_map(data['links'])['public_web']) != null)
              Padding(
                padding: const EdgeInsets.only(top: 18),
                child: OutlinedButton.icon(
                  onPressed: () => _copyPublicLink(data),
                  icon: const Icon(Icons.link_rounded),
                  label: const Text('Copier mon lien public'),
                ),
              ),
          ],
        );
      },
    ),
  );
}

class _PassportBody extends StatelessWidget {
  const _PassportBody({required this.data, required this.baseUri});
  final Map<String, dynamic> data;
  final Uri baseUri;

  static Map<String, dynamic> _map(Object? raw) => raw is Map
      ? raw.map((key, item) => MapEntry(key.toString(), item))
      : <String, dynamic>{};
  static String? _text(Object? value) =>
      value is String && value.trim().isNotEmpty ? value.trim() : null;
  static List<Map<String, dynamic>> _rows(Object? value) => value is List
      ? value.whereType<Map>().map(_map).toList() : const [];

  @override
  Widget build(BuildContext context) {
    final identity = _map(data['identity']);
    final declared = _map(data['declared']);
    final established = _map(data['established']);
    final issued = _map(data['issued']);
    final disclosure = _map(data['disclosure']);
    final name = _text(identity['display_name']) ??
        _text(identity['name']) ?? _text(identity['username']) ??
        'Mon passeport';
    final bio = _text(identity['bio']);
    final profession = _text(identity['profession']);
    final location = _text(identity['location']);
    final avatar = _text(identity['avatar_url']);
    final avatarUri = avatar == null ? null :
        (avatar.startsWith('/') && !avatar.startsWith('//')
            ? baseUri.resolve(avatar)
            : Uri.tryParse(avatar));
    final safeAvatar = avatarUri != null &&
        (avatarUri.scheme == 'https' || avatarUri.scheme == 'http') &&
        avatarUri.host == baseUri.host;
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Container(
        padding: const EdgeInsets.all(22),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [MakoloColors.indigo, MakoloColors.deep],
          ),
          borderRadius: BorderRadius.circular(MakoloRadii.large),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            if (safeAvatar)
              ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: Image.network(avatarUri.toString(), width: 54, height: 54,
                  fit: BoxFit.cover,
                  errorBuilder: (_, _, _) => const Icon(
                    Icons.badge_outlined, color: Colors.white, size: 42),
                ),
              )
            else
              const Icon(Icons.badge_outlined, color: Colors.white, size: 42),
            const Spacer(),
            Text('MAKOLO', style: Theme.of(context).textTheme.labelMedium
              ?.copyWith(color: Colors.white70, letterSpacing: 2)),
          ]),
          const SizedBox(height: 18),
          Text(name, style: Theme.of(context).textTheme.headlineSmall
              ?.copyWith(color: Colors.white, fontWeight: FontWeight.w800)),
          if (profession != null) Text(profession,
              style: Theme.of(context).textTheme.bodyMedium
                  ?.copyWith(color: Colors.white70)),
          if (location != null) Text(location,
              style: Theme.of(context).textTheme.bodySmall
                  ?.copyWith(color: Colors.white70)),
        ]),
      ),
      if (bio != null) Padding(
        padding: const EdgeInsets.only(top: 18),
        child: Text(bio, style: Theme.of(context).textTheme.bodyLarge),
      ),
      const SizedBox(height: 14),
      Wrap(spacing: 10, runSpacing: 8, children: [
        _stat(context, 'Déclaré', disclosure['declared_count']),
        _stat(context, 'Établi', disclosure['established_count']),
        _stat(context, 'Délivré', disclosure['issued_count']),
      ]),
      _section(context, 'Mes intérêts', _rows(declared['interests']),
          (row) => _text(_map(row['topic'])['label'])),
      _section(context, 'Ouvert à', _rows(declared['open_to']),
          (row) => _text(row['label'])),
      _section(context, 'Mes activités', _rows(data['activities']),
          (row) => _text(row['title'])),
      _section(context, 'Faits établis', _rows(established['proofs']),
          (row) => _text(row['proof_type_label'])),
      _section(context, 'Attestations', _rows(issued['credentials']),
          (row) => _text(row['title'])),
    ]);
  }

  Widget _stat(BuildContext context, String label, Object? value) =>
      Chip(label: Text('$label · ${value is int ? value : 0}'));

  Widget _section(BuildContext context, String title,
      List<Map<String, dynamic>> rows,
      String? Function(Map<String, dynamic>) label) {
    final titles = rows.map(label).whereType<String>().toList();
    if (titles.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Text(title, style: Theme.of(context).textTheme.titleLarge
            ?.copyWith(fontWeight: FontWeight.w800)),
        const SizedBox(height: 7),
        for (final value in titles)
          ListTile(dense: true, contentPadding: EdgeInsets.zero,
            title: Text(value)),
      ]),
    );
  }
}
