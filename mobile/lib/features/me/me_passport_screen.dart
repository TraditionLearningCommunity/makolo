import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:flutter/services.dart';

import '../../design/makolo_theme.dart';
import '../../network/makolo_api_client.dart';
import '../../sync/projection_contract.dart';
import '../../repositories/personal_repository.dart';
import 'me_local_preview.dart';

/// Native presentation of the same server-owned Passport variants as Web.
class MePassportScreen extends StatefulWidget {
  const MePassportScreen({super.key, required this.api, this.personal, this.onEdit});
  final MakoloApiClient api;
  final PersonalRepository? personal;
  final VoidCallback? onEdit;
  @override
  State<MePassportScreen> createState() => _MePassportScreenState();
}

class _MePassportScreenState extends State<MePassportScreen> {
  String _variant = 'complete';
  String? _topic;
  final Set<String> _sections = {
    'bio', 'links', 'location', 'profession', 'interests', 'open_to',
  };
  Set<String> _activities = {}, _proofs = {}, _credentials = {};
  Map<String, dynamic>? _full;
  bool _exporting = false;
  bool _onlineReady = false;
  int _loadEpoch = 0;
  Map<String, dynamic>? _localIdentity;
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _restoreIdentity();
    _future = _load();
  }

  Future<void> _restoreIdentity() async {
    final personal = widget.personal;
    if (personal == null) return;
    try {
      final local = MeLocalPreview.forProfile(
        await personal.store.readProjection('personal.me'),
        personal.store.profileId,
      );
      if (mounted && local?.identity != null) {
        setState(() => _localIdentity = local!.identity);
      }
    } on Object {
      // No locally authorized identity: retain the explicit unavailable state.
    }
  }

  Map<String, dynamic> _passportParams() {
    final params = <String, dynamic>{'variant': _variant};
    if (_variant == 'thematic' && _topic != null) params['topic'] = _topic;
    if (_variant == 'custom') {
      params['include'] = _sections.toList();
      params['activity'] = _activities.toList();
      params['proof'] = _proofs.toList();
      params['credential'] = _credentials.toList();
    }
    return params;
  }

  Future<Map<String, dynamic>> _load() async {
    final epoch = ++_loadEpoch;
    final requestedVariant = _variant;
    final url = Uri(path: 'api/v1/me/passport/',
      queryParameters: _passportParams()).toString();
    final response = await widget.api.get(url);
    final data = ProjectionEnvelope.parse(
      response.jsonObject(), expectedProjection: 'personal.me.passport',
    ).data;
    // An older in-flight response can never authorize a different variant.
    if (epoch != _loadEpoch ||
        requestedVariant != _variant ||
        data['variant'] != requestedVariant) {
      throw const FormatException('Outdated or invalid Passport variant');
    }
    if (mounted) setState(() => _onlineReady = true);
    if (requestedVariant == 'complete') {
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
    setState(() { _variant = variant; _onlineReady = false; _future = _load(); });
  }

  Future<void> _copyPublicLink() async {
    // A displayed passport is not permission to disclose it later. The
    // server must confirm public exposure at the moment the link is copied.
    try {
      final current = await _load();
      if (!mounted ||
          _map(current['projection'])['public_profile_enabled'] != true) {
        return;
      }
      final path = _text(_map(current['links'])['public_web']);
      if (path == null || !path.startsWith('/') || path.startsWith('//')) {
        return;
      }
      final uri = widget.api.baseUri.resolve(path);
      await Clipboard.setData(ClipboardData(text: uri.toString()));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Lien public copié.')),
        );
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Impossible de vérifier le lien public.'),
        ));
      }
    }
  }

  Future<String?> _downloadPassport() async {
    if (_exporting) return null;
    setState(() => _exporting = true);
    try {
      final directory = await getTemporaryDirectory();
      final file = '${directory.path}/passeport-makolo-$_variant.pdf';
      final url = Uri(path: 'api/v1/me/passport/pdf/',
        queryParameters: _passportParams()).toString();
      await widget.api.download(url, destinationPath: file);
      return file;
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Exportation du Passeport indisponible.'),
        ));
      }
      return null;
    } finally {
      if (mounted) setState(() => _exporting = false);
    }
  }

  Future<void> _exportPdf() async {
    final file = await _downloadPassport();
    if (file == null || !mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
      content: Text('Passeport PDF préparé.'),
    ));
    await SharePlus.instance.share(ShareParams(
      files: [XFile(file, mimeType: 'application/pdf')],
      subject: 'Passeport Makolo',
    ));
  }

  Future<void> _sharePassport(Map<String, dynamic> data) async {
    final publicPath = _text(_map(data['links'])['public_web']);
    final canShareLink = _variant == 'public' &&
        _map(data['projection'])['public_profile_enabled'] == true &&
        publicPath != null && publicPath.startsWith('/') &&
        !publicPath.startsWith('//');
    final action = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          ListTile(
            leading: const Icon(Icons.picture_as_pdf_outlined),
            title: const Text('Partager le PDF'),
            onTap: () => Navigator.pop(context, 'pdf'),
          ),
          if (canShareLink)
            ListTile(
              leading: const Icon(Icons.link_rounded),
              title: const Text('Partager le lien public'),
              onTap: () => Navigator.pop(context, 'link'),
            ),
        ]),
      ),
    );
    if (action == null || !mounted) return;
    if (action == 'pdf' && _variant != 'public') {
      final consent = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Partager ce Passeport ?'),
          content: const Text(
            'Le PDF peut contenir des informations personnelles. '
            'Les personnes qui le reçoivent pourront le conserver.',
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false),
              child: const Text('Annuler')),
            FilledButton(onPressed: () => Navigator.pop(context, true),
              child: const Text('Partager')),
          ],
        ),
      );
      if (consent != true || !mounted) return;
    }
    if (action == 'link') {
      final url = widget.api.baseUri.resolve(publicPath!).toString();
      await SharePlus.instance.share(ShareParams(text: url,
        subject: 'Passeport Makolo'));
      return;
    }
    await _exportPdf();
  }

  void _toggle(Set<String> values, String id, bool enabled) {
    setState(() {
      if (enabled) { values.add(id); } else { values.remove(id); }
      _onlineReady = false;
      _future = _load();
    });
  }

  Widget _localPassportSummary(BuildContext context, {bool refreshing = false}) {
    final identity = _localIdentity;
    final name = identity?['display_name']?.toString();
    final bio = identity?['bio']?.toString();
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 24, 16, 40),
      children: [
        Text(
          identity == null
              ? 'Passeport non encore disponible sur cet appareil.'
              : 'Aperçu local de Moi. Le Passeport détaillé et ses variantes '
                  'nécessitent une actualisation du serveur.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        if (name != null && name.trim().isNotEmpty) ...[
          const SizedBox(height: 20),
          Text(name, style: Theme.of(context).textTheme.headlineSmall),
        ],
        if (bio != null && bio.trim().isNotEmpty) ...[
          const SizedBox(height: 12),
          Text(bio),
        ],
        const SizedBox(height: 20),
        if (refreshing) ...[
          const LinearProgressIndicator(minHeight: 2),
          const SizedBox(height: 12),
          const Text('Actualisation du Passeport en cours…'),
        ],
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            onPressed: refreshing ? null : () => setState(() {
              _onlineReady = false;
              _future = _load();
            }),
            icon: const Icon(Icons.refresh_rounded),
            label: const Text('Réessayer'),
          ),
        ),
        const Text(
          'L’export PDF et le partage sont indisponibles sans confirmation '
          'du serveur.',
        ),
      ],
    );
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
            initialValue: _topic,
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
              _onlineReady = false;
              _future = _load();
            }),
          ),
      ],
      if (_variant == 'custom') ...[
        const SizedBox(height: 14),
        Text('À présenter', style: theme.textTheme.titleMedium),
        Wrap(spacing: 6, children: [
          for (final option in const [
            ('bio', 'À propos'), ('profession', 'Profession'),
            ('location', 'Localisation'), ('links', 'Liens'),
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
    appBar: AppBar(
      title: const Text('Passeport Makolo'),
      actions: [
        IconButton(
          tooltip: 'Exporter le Passeport en PDF',
          onPressed: _exporting || !_onlineReady ? null : _exportPdf,
          icon: const Icon(Icons.picture_as_pdf_outlined),
        ),
        IconButton(
          tooltip: 'Partager le Passeport',
          onPressed: _exporting || !_onlineReady ? null : () async {
            // Revalidate public disclosure before building any share action.
            setState(() => _onlineReady = false);
            try {
              final data = await _load();
              if (mounted) await _sharePassport(data);
            } on Object {
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                  content: Text('Partage indisponible sans connexion.'),
                ));
              }
            }
          },
          icon: const Icon(Icons.share_outlined),
        ),
        if (widget.onEdit != null)
          IconButton(
            tooltip: 'Modifier mon passeport',
            icon: const Icon(Icons.edit_outlined),
            onPressed: widget.onEdit,
          ),
      ],
    ),
    body: FutureBuilder<Map<String, dynamic>>(
      future: _future,
      builder: (context, snapshot) {
        // FutureBuilder may retain the previous variant while a new request
        // is pending. Never show that data as if it were the new variant.
        if (snapshot.connectionState != ConnectionState.done) {
          return _localIdentity == null
              ? const Center(child: CircularProgressIndicator.adaptive())
              : _localPassportSummary(context, refreshing: true);
        }
        if (!snapshot.hasData) {
          return _localPassportSummary(context);
        }
        final data = snapshot.data!;
        return ListView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
          children: [
            _options(data),
            const SizedBox(height: 16),
            _PassportBody(data: data, baseUri: widget.api.baseUri),
            if (widget.onEdit != null)
              Padding(
                padding: const EdgeInsets.only(top: 16),
                child: OutlinedButton.icon(
                  onPressed: widget.onEdit,
                  icon: const Icon(Icons.edit_outlined),
                  label: const Text('Modifier le Passeport'),
                ),
              ),
            if (_map(data['projection'])['public_profile_enabled'] == true &&
                _text(_map(data['links'])['public_web']) != null)
              Padding(
                padding: const EdgeInsets.only(top: 18),
                child: OutlinedButton.icon(
                  onPressed: _copyPublicLink,
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
    final links = _rows(identity['links']);
    final privateDetails = _map(data['private_details']);
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
      if (privateDetails.isNotEmpty) _personalDetails(context, privateDetails),
      if (bio != null) Padding(
        padding: const EdgeInsets.only(top: 18),
        child: Text(bio, style: Theme.of(context).textTheme.bodyLarge),
      ),
      if (links.isNotEmpty) ...[
        const SizedBox(height: 18),
        Text('Liens', style: Theme.of(context).textTheme.titleLarge
            ?.copyWith(fontWeight: FontWeight.w800)),
        for (final link in links)
          if (_text(link['label']) != null && _text(link['url']) != null)
            ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              title: Text(link['label'].toString()),
              subtitle: SelectableText(link['url'].toString()),
            ),
      ],
      const SizedBox(height: 14),
      Wrap(spacing: 10, runSpacing: 8, children: [
        _stat(context, 'Déclaré', disclosure['declared_count']),
        _stat(context, 'Établi', disclosure['established_count']),
        _stat(context, 'Délivré', disclosure['issued_count']),
      ]),
      _section(context, 'Centres d’intérêt', _rows(declared['interests']),
          (row) => _text(_map(row['topic'])['label'])),
      _section(context, 'Ouvert à', _rows(declared['open_to']),
          (row) => _text(row['label'])),
      _section(context, 'Activités', _rows(data['activities']),
          (row) => _text(row['title'])),
      _section(context, 'Faits établis', _rows(established['proofs']),
          (row) => _text(row['proof_type_label'])),
      _section(context, 'Attestations', _rows(issued['credentials']),
          (row) => _text(row['title'])),
    ]);
  }

  Widget _personalDetails(BuildContext context, Map<String, dynamic> details) {
    const fields = <(String, String)>[
      ('first_name', 'Prénom'),
      ('last_name', 'Nom'),
      ('username', 'Identifiant Makolo'),
      ('company', 'Entreprise'),
      ('organization', 'Organisation'),
      ('city', 'Ville'),
      ('country', 'Pays'),
      ('language', 'Langue'),
      ('phone', 'Téléphone'),
      ('address', 'Adresse'),
      ('birth_date', 'Date de naissance'),
      ('gender', 'Genre'),
    ];
    final visible = [
      for (final field in fields)
        if (_text(details[field.$1]) != null) field,
    ];
    if (visible.isEmpty) return const SizedBox.shrink();
    final colors = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(top: 24),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(Icons.person_outline_rounded, color: colors.primary, size: 21),
          const SizedBox(width: 9),
          Text('Informations personnelles', style: Theme.of(context).textTheme.titleLarge
              ?.copyWith(fontWeight: FontWeight.w800)),
        ]),
        const SizedBox(height: 4),
        Text('Visible uniquement dans mon passeport complet',
          style: Theme.of(context).textTheme.bodySmall
              ?.copyWith(color: colors.onSurfaceVariant)),
        const SizedBox(height: 12),
        for (final field in visible)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 7),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              SizedBox(width: 126, child: Text(field.$2,
                style: Theme.of(context).textTheme.bodySmall
                    ?.copyWith(color: colors.onSurfaceVariant))),
              const SizedBox(width: 8),
              Expanded(child: SelectableText(details[field.$1].toString(),
                style: Theme.of(context).textTheme.bodyMedium
                    ?.copyWith(fontWeight: FontWeight.w600))),
            ]),
          ),
      ]),
    );
  }

  Widget _stat(BuildContext context, String label, Object? value) {
    final colors = Theme.of(context).colorScheme;
    final count = value is int ? value : 0;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(100),
        color: colors.primary.withValues(alpha: 0.07),
      ),
      child: Text('$label · $count',
        style: Theme.of(context).textTheme.labelMedium?.copyWith(
          color: colors.onSurface,
          fontWeight: FontWeight.w700,
        )),
    );
  }

  Widget _section(BuildContext context, String title,
      List<Map<String, dynamic>> rows,
      String? Function(Map<String, dynamic>) label) {
    final titles = rows.map(label).whereType<String>().toSet().toList();
    if (titles.isEmpty) return const SizedBox.shrink();
    final colors = Theme.of(context).colorScheme;
    final isInterest = title == 'Centres d’intérêt';
    final isOpening = title == 'Ouvert à';
    final isDeclared = isInterest || isOpening;
    final icon = isInterest ? Icons.interests_outlined
        : isOpening ? Icons.handshake_outlined
        : title == 'Mes activités' ? Icons.event_available_outlined
        : title == 'Faits établis' ? Icons.verified_outlined
        : Icons.workspace_premium_outlined;
    return Padding(
      padding: const EdgeInsets.only(top: 28),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(icon, size: 21, color: colors.primary),
          const SizedBox(width: 9),
          Expanded(
            child: Text(title, style: Theme.of(context).textTheme.titleLarge
                ?.copyWith(fontWeight: FontWeight.w800)),
          ),
          Text('${titles.length}', style: Theme.of(context).textTheme.labelLarge
              ?.copyWith(color: colors.onSurfaceVariant)),
        ]),
        const SizedBox(height: 12),
        if (isDeclared)
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final value in titles)
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 13, vertical: 9),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(100),
                    color: colors.primary.withValues(alpha: 0.07),
                    border: Border.all(
                      color: colors.primary.withValues(alpha: 0.15)),
                  ),
                  child: Text(value,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w600)),
                ),
            ],
          )
        else
          Column(
            children: [
              for (var index = 0; index < titles.length; index++) ...[
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: colors.primary.withValues(alpha: 0.08),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Icon(icon, size: 18, color: colors.primary),
                    ),
                    const SizedBox(width: 12),
                    Expanded(child: Text(titles[index],
                      style: Theme.of(context).textTheme.bodyLarge)),
                  ]),
                ),
                if (index != titles.length - 1)
                  Divider(height: 1, color: colors.outlineVariant),
              ],
            ],
          ),
      ]),
    );
  }

}
