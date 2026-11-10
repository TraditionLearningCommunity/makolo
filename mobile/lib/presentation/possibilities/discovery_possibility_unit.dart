import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../design/action_controls.dart';
import '../../design/behavior_primitives.dart';
import '../../design/makolo_patterns.dart';
import '../../design/makolo_theme.dart';
import '../../network/makolo_api_client.dart';
import '../../features/discovery/discovery_share_sheet.dart';
import '../../features/discovery/discovery_selector.dart';
import 'discovery_reader.dart';
import 'discovery_n2_depth.dart';
import 'discovery_save_icon.dart';

export 'discovery_save_icon.dart' show DiscoveryOrbitIcon;

/// Ephemeral viewer-scoped UI feedback shared by cards of the same publisher.
/// Server Discovery remains authoritative; no relationships are persisted here.
class DiscoveryFollowScope extends StatefulWidget {
  const DiscoveryFollowScope({
    super.key,
    required this.profileId,
    required this.child,
  });

  final String? profileId;
  final Widget child;

  static DiscoveryFollowController? maybeOf(BuildContext context) => context
      .dependOnInheritedWidgetOfExactType<_DiscoveryFollowInherited>()
      ?.controller;

  @override
  State<DiscoveryFollowScope> createState() => _DiscoveryFollowScopeState();
}

class DiscoveryFollowController extends ChangeNotifier {
  final Map<String, bool> _confirmed = <String, bool>{};

  bool? followedFor(String key) => _confirmed[key];

  void confirm(String key, bool followed) {
    _confirmed[key] = followed;
    notifyListeners();
  }

  void clear() {
    _confirmed.clear();
    notifyListeners();
  }
}

class _DiscoveryFollowScopeState extends State<DiscoveryFollowScope> {
  final DiscoveryFollowController _controller = DiscoveryFollowController();

  @override
  void didUpdateWidget(covariant DiscoveryFollowScope oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.profileId != widget.profileId) {
      _controller.clear();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => _DiscoveryFollowInherited(
    controller: _controller,
    notifier: _controller,
    child: widget.child,
  );
}

class _DiscoveryFollowInherited
    extends InheritedNotifier<DiscoveryFollowController> {
  const _DiscoveryFollowInherited({
    required this.controller,
    required super.notifier,
    required super.child,
  });

  final DiscoveryFollowController controller;
}

/// Locale-aware compact label for the time a possibility was *added*.
///
/// This is intentionally unrelated to the timing of an Occurrence. The exact
/// timestamp remains accessible through the tooltip/semantics of N1.
String discoveryAddedAtLabel(
  DateTime addedAt,
  DateTime now, {
  bool french = true,
}) {
  final local = addedAt.toLocal();
  final current = now.toLocal();
  final duration = current.difference(local);
  if (duration.isNegative) return '';
  final day = DateTime(local.year, local.month, local.day);
  final today = DateTime(current.year, current.month, current.day);
  final calendarDays = today.difference(day).inDays;
  if (calendarDays == 0) {
    if (duration.inMinutes < 1) {
      return french ? 'À l’instant' : 'Just now';
    }
    if (duration.inHours < 1) {
      return french
          ? 'il y a ${duration.inMinutes} min'
          : '${duration.inMinutes} min ago';
    }
    return french
        ? 'il y a ${duration.inHours} h'
        : '${duration.inHours} h ago';
  }
  if (calendarDays == 1) return french ? 'Hier' : 'Yesterday';
  if (calendarDays == 2) return french ? 'Avant-hier' : 'Two days ago';
  if (calendarDays < 7) {
    return french ? 'il y a $calendarDays j' : '$calendarDays days ago';
  }
  if (calendarDays < 30) {
    final weeks = calendarDays ~/ 7;
    return french ? 'il y a $weeks sem.' : '$weeks weeks ago';
  }
  return '';
}

/// This is route availability, not authorization. The owner checks any
/// protected mutation when it is actually requested.
bool discoveryOwnerDepthBrowsableByGuest(String path) {
  final parts = path.split('/');
  if (parts.isEmpty || parts.first.isNotEmpty) return false;
  if (parts.length == 4) {
    return parts[2].isNotEmpty &&
        ((parts[1] == 'events' && parts[3] == 'tickets') ||
            (parts[1] == 'funding' && parts[3] == 'contribute') ||
            (parts[1] == 'obtention' && parts[3] == 'choose'));
  }
  return parts.length == 5 &&
      parts[1] == 'commerce' &&
      parts[2] == 'activities' &&
      parts[3].isNotEmpty &&
      parts[4] == 'checkout';
}

/// The existing Discovery projection rendered as one N1 unit.
/// Facts and actions remain owned by the server; this widget only composes.
class DiscoveryPossibilityUnit extends StatefulWidget {
  const DiscoveryPossibilityUnit({
    super.key,
    required this.item,
    required this.onOpen,
    this.onSave,
    this.allowSavePrompt = false,
    this.shareApi,
    this.shareAuthenticated = false,
    this.onSignIn,
    this.onSelect,
    this.selectionActionLabel,
    this.baseUri,
    this.profileId,
    this.allowOwnerActions = true,
    this.collectiveReadOnly = false,
    this.compact = false,
    this.detailMode = false,
    this.onNativeAction,
    this.onOwnerDepth,
  });

  final DiscoveryItemPresentation item;
  final VoidCallback onOpen;
  final Future<void> Function()? onSave;
  final bool allowSavePrompt;
  final MakoloApiClient? shareApi;
  final bool shareAuthenticated;
  final VoidCallback? onSignIn;
  final VoidCallback? onSelect;
  final String? selectionActionLabel;
  final Uri? baseUri;
  final String? profileId;

  /// Cached recognition is not a live authorization from the owner.
  final bool allowOwnerActions;

  /// Space detail keeps published facts without personal Save/Share chrome.
  final bool collectiveReadOnly;
  final bool compact;

  /// Renders the same server-owned facts at N2 without repeating N1 chrome.
  final bool detailMode;

  /// Guest entry may resume the owner route after session recovery.
  final ValueChanged<String>? onNativeAction;

  /// Optional N3 read-only owner depth. No action or authority is inferred.
  final ValueChanged<String>? onOwnerDepth;

  @override
  State<DiscoveryPossibilityUnit> createState() =>
      _DiscoveryPossibilityUnitState();
}

class _DiscoveryPossibilityUnitState extends State<DiscoveryPossibilityUnit> {
  bool _saving = false;
  bool _saveFailed = false;
  bool _expanded = false;
  int _galleryPage = 0;
  bool _allResources = false;
  bool? _confirmedSaved;
  bool _followingBusy = false;
  bool? _confirmedFollowed;

  @override
  void didUpdateWidget(covariant DiscoveryPossibilityUnit oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.item.candidateKey != widget.item.candidateKey ||
        (_confirmedSaved != null &&
            widget.item.savedState ==
                (_confirmedSaved! ? 'saved' : 'not_saved'))) {
      _confirmedSaved = null;
      _saveFailed = false;
    }
    if (oldWidget.item.candidateKey != widget.item.candidateKey ||
        oldWidget.item.ownerFacts?['identity'].toString() !=
            widget.item.ownerFacts?['identity'].toString()) {
      _confirmedFollowed = null;
      _followingBusy = false;
    }
    if (_confirmedFollowed != null &&
        widget.item.ownerFacts?['follow'] is Map &&
        (widget.item.ownerFacts!['follow'] as Map)['followed'] ==
            _confirmedFollowed) {
      _confirmedFollowed = null;
    }
    if (oldWidget.item.candidateKey != widget.item.candidateKey) {
      _expanded = false;
      _galleryPage = 0;
      _allResources = false;
    }
  }

  Future<void> _save() async {
    if (_saving) return;
    // A guest prompt is navigation, not an optimistic owner mutation.
    if (widget.allowSavePrompt && widget.onSignIn != null) {
      widget.onSignIn!();
      return;
    }
    if (widget.onSave == null) return;
    final previousState = widget.item.savedState;
    final candidateKey = widget.item.candidateKey;
    setState(() {
      _saving = true;
      _saveFailed = false;
    });
    try {
      await widget.onSave!();
      if (mounted &&
          widget.item.candidateKey == candidateKey &&
          !widget.allowSavePrompt &&
          widget.item.savedState == previousState) {
        setState(() => _confirmedSaved = previousState != 'saved');
      }
    } on Object {
      if (mounted && widget.item.candidateKey == candidateKey) {
        setState(() => _saveFailed = true);
        showMakoloNotice(
          context,
          'L’enregistrement n’a pas pu être confirmé.',
          kind: MakoloNoticeKind.error,
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  /// Only a signed-in viewer can act on a server-projected public owner.
  Map<String, dynamic>? get _followTarget {
    if (!widget.allowOwnerActions ||
        widget.collectiveReadOnly ||
        !widget.shareAuthenticated ||
        widget.shareApi == null) {
      return null;
    }
    final owner = widget.item.ownerFacts;
    final identity = owner?['identity'];
    final follow = owner?['follow'];
    if (identity is! Map ||
        follow is! Map ||
        follow['can_toggle'] != true ||
        follow['followed'] is! bool) {
      return null;
    }
    final kind = identity['kind'];
    final id = identity['id'];
    if ((kind != 'space' && kind != 'profile') ||
        id is! String ||
        !RegExp(r'^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$')
            .hasMatch(id)) {
      return null;
    }
    return {'kind': kind, 'id': id, 'followed': follow['followed']};
  }

  Future<void> _toggleFollow() async {
    final target = _followTarget;
    final api = widget.shareApi;
    if (_followingBusy || target == null || api == null) return;
    final key = '${target['kind']}:${target['id']}';
    final followScope = DiscoveryFollowScope.maybeOf(context);
    final currentlyFollowed =
        followScope?.followedFor(key) ??
        _confirmedFollowed ??
        (target['followed'] == true);
    final endpoint =
        'api/v1/organizations/follows/targets/${target['kind']}/${target['id']}/';
    setState(() => _followingBusy = true);
    try {
      final response = currentlyFollowed
          ? await api.delete(endpoint)
          : await api.post(endpoint);
      final result = response.jsonObject();
      if (result['followed'] is! bool) {
        throw const FormatException('État du suivi non confirmé');
      }
      if (!mounted) return;
      final current = _followTarget;
      if (current != null && '${current['kind']}:${current['id']}' == key) {
        final confirmed = result['followed'] as bool;
        setState(() => _confirmedFollowed = confirmed);
        followScope?.confirm(key, confirmed);
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Le suivi n’a pas pu être confirmé.')),
        );
      }
    } finally {
      if (mounted) setState(() => _followingBusy = false);
    }
  }

  DiscoveryItemPresentation get item => widget.item;

  /// Fact values belong to the server. UI deduplicates presentation aliases,
  /// never guesses an unknown price or capacity from editorial text.
  List<Map<String, dynamic>> get _reliableFacts {
    final facts = <Map<String, dynamic>>[];
    final seenCodes = <String>{};
    final seenLabels = <String>{};

    String canonicalCode(String code) {
      switch (code.toLowerCase().trim()) {
        case 'availability':
        case 'capacity':
          return 'capacity';
        case 'start_at':
        case 'start_date':
        case 'when':
          return 'when';
        case 'primary_place':
        case 'place_primary':
        case 'place':
          return 'place';
        default:
          return code.toLowerCase().trim();
      }
    }

    void add(String code, String label, String? value) {
      final normalizedValue = value?.trim() ?? '';
      final normalizedLabel = label.trim().toLowerCase();
      final normalizedCode = canonicalCode(code);
      final lowercaseValue = normalizedValue.toLowerCase();
      // Missing/uncertain information is not a practical fact.
      const placeholders = {
        'unknown',
        'inconnu',
        'inconnue',
        'non renseigné',
        'non renseignée',
        'non précisé',
        'non précisée',
        'à déterminer',
        'à compléter',
        'à confirmer',
        'disponibilité à confirmer',
        'n/a',
        '—',
      };
      if (placeholders.contains(lowercaseValue) ||
          lowercaseValue.endsWith(' à confirmer') ||
          lowercaseValue.endsWith(' à déterminer') ||
          lowercaseValue.endsWith(' à compléter')) {
        return;
      }
      if (normalizedValue.isEmpty ||
          normalizedLabel.isEmpty ||
          normalizedCode == 'type' ||
          normalizedLabel == 'type' ||
          seenCodes.contains(normalizedCode) ||
          seenLabels.contains(normalizedLabel)) {
        return;
      }
      seenCodes.add(normalizedCode);
      seenLabels.add(normalizedLabel);
      facts.add({
        'code': normalizedCode,
        'label': label,
        'value': normalizedValue,
      });
    }

    for (final fact in item.presentationFacts) {
      final label = fact['label'];
      final value = fact['value'];
      if (label is String && value is String) {
        add((fact['code'] ?? label).toString(), label, value);
      }
    }
    add('price', 'Prix', item.price);
    add('when', 'Quand', item.timing);
    add('place', 'Lieu', item.place);
    if (item.availabilityFacts?['state'] != 'unknown') {
      add('capacity', 'Disponibilité', item.availability);
    }
    add('route', 'Trajet', item.routeLabel);
    const dates = {
      'start_at': 'Début',
      'end_at': 'Fin',
      'start_date': 'Début',
      'end_date': 'Fin',
      'opens_at': 'Ouverture',
      'closes_at': 'Clôture',
      'deadline_at': 'Date limite',
    };
    for (final fact in item.temporalFacts) {
      final kind = fact['kind']?.toString() ?? '';
      final label = dates[kind];
      if (label != null) {
        add(kind, label, fact['value']?.toString());
      }
    }
    const roleLabels = {
      'primary': 'Lieu',
      'venue': 'Lieu',
      'departure': 'Départ',
      'arrival': 'Arrivée',
      'stopover': 'Escale',
      'boarding': 'Embarquement',
      'dropoff': 'Débarquement',
    };
    final roleCounts = <String, int>{};
    for (final fact in item.spatialFacts) {
      final role = (fact['role'] ?? '').toString().toLowerCase();
      roleCounts[role] = (roleCounts[role] ?? 0) + 1;
    }
    final rolePositions = <String, int>{};
    for (final fact in item.spatialFacts) {
      final role = (fact['role'] ?? '').toString().toLowerCase();
      final place = fact['place'];
      if (place is Map) {
        final name = (place['name'] ?? '').toString().trim();
        final locality = (place['locality'] ?? '').toString().trim();
        final value =
            name.isNotEmpty &&
                locality.isNotEmpty &&
                name.toLowerCase() != locality.toLowerCase()
            ? '$name, $locality'
            : name.isNotEmpty
            ? name
            : locality;
        if (value.isEmpty) continue;
        final ordinal = (rolePositions[role] ?? 0) + 1;
        rolePositions[role] = ordinal;
        final repeated = (roleCounts[role] ?? 0) > 1;
        final label = roleLabels[role] ?? 'Lieu';
        add(
          repeated
              ? 'place_${role}_$ordinal'
              : (role == 'primary' || role == 'venue'
                    ? 'place'
                    : 'place_$role'),
          repeated ? '$label $ordinal' : label,
          value,
        );
      }
    }
    final personal = (item.participantPresentation?['label'] ?? '')
        .toString()
        .trim();
    if (personal.isNotEmpty) add('personal_state', 'Ma situation', personal);
    return facts;
  }

  /// Context does not turn an unknown fact into a client-side assertion.
  /// These are owner-projected limitations and counts of actual relations.
  List<String> get _contextNotes {
    final notes = <String>[];
    final assessment = item.wire['assessment'];
    if (assessment is List) {
      for (final raw in assessment) {
        if (raw is! Map || raw['state'] != 'limiting') continue;
        final label = (raw['label'] ?? '').toString().trim();
        if (label.isNotEmpty && !notes.contains(label)) notes.add(label);
      }
    }
    if (item.variants.length > 1) {
      notes.add('${item.variants.length} variantes');
    }
    if (item.relations.isNotEmpty) {
      notes.add('${item.relations.length} relations');
    }
    return notes;
  }

  List<Map<String, String?>> get _resourceEntries {
    final entries = <Map<String, String?>>[];
    final resources = item.wire['resources'];
    if (resources is! List) return entries;
    for (final raw in resources) {
      if (raw is! Map) continue;
      final title = (raw['title'] ?? '').toString().trim();
      if (title.isEmpty) continue;
      final mime = (raw['mime_type'] ?? '').toString().toLowerCase();
      entries.add({
        'label': title,
        'mime': mime,
        'title': title,
        'kind': raw['kind']?.toString(),
        'text': raw['kind'] == 'text' ? raw['text_content']?.toString() : null,
        'url': raw['kind'] == 'file'
            ? raw['download_url']?.toString()
            : raw['kind'] == 'url'
            ? raw['external_url']?.toString()
            : raw['kind'] == 'text'
            ? raw['read_url']?.toString()
            : null,
      });
    }
    return entries;
  }

  void _openReader(List<DiscoveryReaderItem> items, {int index = 0}) {
    if (items.isEmpty) return;
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => DiscoveryReader(
          items: items,
          initialIndex: index,
          profileId: widget.profileId,
          trustedOrigin: widget.baseUri,
        ),
      ),
    );
  }

  Future<void> _openWebsite(Uri uri) async {
    try {
      final opened = await launchUrl(uri, mode: LaunchMode.inAppBrowserView);
      if (!opened && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Cette page ne peut pas être ouverte ici.'),
          ),
        );
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Cette page ne peut pas être ouverte ici.'),
          ),
        );
      }
    }
  }

  IconData _resourceIcon(Map<String, String?> resource) {
    final kind = resource['kind'] ?? '';
    final mime = (resource['mime'] ?? '').toLowerCase();
    if (kind == 'url') return Icons.language_rounded;
    if (mime.startsWith('image/')) return Icons.image_outlined;
    if (mime.startsWith('video/')) return Icons.movie_outlined;
    if (mime.startsWith('audio/')) return Icons.audiotrack_outlined;
    if (mime == 'application/pdf') return Icons.picture_as_pdf_outlined;
    if (mime.contains('spreadsheet') ||
        mime.contains('excel') ||
        mime == 'text/csv') {
      return Icons.table_chart_outlined;
    }
    if (mime.contains('presentation') || mime.contains('powerpoint')) {
      return Icons.slideshow_outlined;
    }
    if (kind == 'text' || mime.startsWith('text/')) {
      return Icons.article_outlined;
    }
    return Icons.description_outlined;
  }

  void _openResource(Map<String, String?> resource) {
    final source = resource['url'];
    final raw = source == null ? null : _publicImage(source);
    final title = resource['title'] ?? resource['label'] ?? 'Ressource';
    if (raw != null) {
      final uri = Uri.parse(raw);
      if (!discoverySafeDestination(uri)) return;
      if (resource['kind'] == 'url') {
        _openWebsite(uri);
        return;
      }
      _openReader([
        DiscoveryReaderItem(
          title: title,
          uri: uri,
          mimeType: resource['kind'] == 'url'
              ? 'text/html'
              : resource['kind'] == 'text'
              ? 'text/plain'
              : resource['mime']?.isNotEmpty == true
              ? resource['mime']!
              : 'application/octet-stream',
        ),
      ]);
      return;
    }
    final text = resource['text'];
    if (text == null || text.isEmpty) return;
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: SingleChildScrollView(child: SelectableText(text)),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Fermer'),
          ),
        ],
      ),
    );
  }

  String? _publicImage(String? source) {
    if (source == null || source.trim().isEmpty) return null;
    final parsed = Uri.tryParse(source);
    if (parsed == null) return null;
    final url = parsed.hasScheme ? parsed : widget.baseUri?.resolveUri(parsed);
    if (url == null ||
        (url.scheme != 'https' && url.scheme != 'http') ||
        url.host.isEmpty) {
      return null;
    }
    return url.toString();
  }

  Widget _media(BuildContext context) {
    final images = <Map<String, String>>[];
    final byUrl = <String, int>{};
    void add(String? source, String label, {String? mimeType}) {
      final url = _publicImage(source);
      if (url == null) return;
      final mime = mimeType == 'image/jpeg' ? 'image/jpeg' : 'image/png';
      final existing = byUrl[url];
      if (existing != null) {
        // The explicit Presentation media-use owns the actual MIME and alt.
        if (mimeType != null) {
          images[existing]['mime'] = mime;
          images[existing]['label'] = label;
        }
        return;
      }
      byUrl[url] = images.length;
      images.add({'url': url, 'label': label, 'mime': mime});
    }

    add(item.imageUrl, 'Visuel de ${item.title}');
    for (final binding in item.mediaBindings) {
      final resource = binding['resource'];
      if (resource is! Map) continue;
      final mime = (resource['mime_type'] ?? '').toString().toLowerCase();
      if (mime != 'image/png' && mime != 'image/jpeg') continue;
      add(
        resource['url']?.toString(),
        (resource['alt_text'] ?? 'Visuel de ${item.title}').toString(),
        mimeType: mime,
      );
    }
    if (images.isEmpty) return const SizedBox.shrink();
    if (images.length == 1) {
      final image = images.first;
      return InkWell(
        key: const Key('discover-media-main'),
        onTap: () => _openReader([
          DiscoveryReaderItem(
            title: image['label']!,
            uri: Uri.parse(image['url']!),
            mimeType: image['mime']!,
          ),
        ]),
        child: Image.network(
          image['url']!,
          width: double.infinity,
          fit: BoxFit.fitWidth,
          semanticLabel: image['label'],
          errorBuilder: (_, _, _) => const SizedBox.shrink(),
        ),
      );
    }
    return Column(
      key: const Key('discover-media-gallery'),
      children: [
        AspectRatio(
          aspectRatio: 4 / 3,
          child: PageView.builder(
            key: ValueKey('discover-gallery-${item.candidateKey}'),
            itemCount: images.length,
            onPageChanged: (index) => setState(() => _galleryPage = index),
            itemBuilder: (context, index) {
              final image = images[index];
              return InkWell(
                onTap: () => _openReader([
                  for (final image in images)
                    DiscoveryReaderItem(
                      title: image['label']!,
                      uri: Uri.parse(image['url']!),
                      mimeType: image['mime']!,
                    ),
                ], index: index),
                child: Image.network(
                  image['url']!,
                  fit: BoxFit.contain,
                  semanticLabel: image['label'],
                  errorBuilder: (_, _, _) =>
                      const Center(child: Text('Image indisponible.')),
                ),
              );
            },
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.xs),
          child: Text(
            '${_galleryPage + 1} / ${images.length} · Faire glisser pour parcourir',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ),
      ],
    );
  }

  Widget _ownerHeader(BuildContext context) {
    final name = item.owner;
    final hasOwner = name != null && name.isNotEmpty;
    if (!hasOwner && item.wire['date'] is! Map) {
      return const SizedBox.shrink();
    }
    final owner = item.ownerFacts;
    final representation = owner?['representation'];
    final ownerLinks = owner?['links'];
    final avatar = representation is Map
        ? _publicImage(representation['avatar_url']?.toString())
        : null;
    final contextFacts = owner?['context'];
    final city = contextFacts is Map ? contextFacts['city'] : null;
    final country = contextFacts is Map ? contextFacts['country'] : null;
    final location = [
      if (city is String && city.trim().isNotEmpty) city.trim(),
      if (country is String && country.trim().isNotEmpty) country.trim(),
    ].join(' · ');
    final ownerKind = owner?['identity'] is Map
        ? (owner!['identity'] as Map)['kind']
        : null;
    final nativePath = ownerLinks is Map ? ownerLinks['native'] : null;
    final followTarget = _followTarget;
    final followKey = followTarget == null
        ? null
        : '${followTarget['kind']}:${followTarget['id']}';
    final followed =
        (followKey == null
            ? null
            : DiscoveryFollowScope.maybeOf(context)?.followedFor(followKey)) ??
        _confirmedFollowed ??
        (followTarget?['followed'] == true);
    final navigable =
        owner?['capabilities'] is List &&
        (owner!['capabilities'] as List).contains('view_public') &&
        nativePath is String &&
        (nativePath.startsWith('/spaces/') ||
            nativePath.startsWith('/people/'));
    return Row(
      key: const Key('discover-owner-date-row'),
      children: [
        if (hasOwner)
          Expanded(
            child: InkWell(
              onTap: navigable ? () => context.push(nativePath) : null,
              onLongPress: navigable
                  ? () => showMakoloQuickPreview(
                      context,
                      title: name,
                      eyebrow: ownerKind == 'space' ? 'Espace' : 'Profil',
                      avatar: avatar == null ? null : NetworkImage(avatar),
                      icon: ownerKind == 'space'
                          ? Icons.business_outlined
                          : Icons.person_outline_rounded,
                      facts: [if (location.isNotEmpty) location],
                      actionLabel: ownerKind == 'space'
                          ? 'Ouvrir l’Espace'
                          : 'Ouvrir le Profil',
                      onOpen: () {
                        if (context.mounted) context.push(nativePath);
                      },
                    )
                  : null,
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 19,
                    foregroundImage: avatar == null
                        ? null
                        : NetworkImage(avatar),
                    child: avatar == null ? Text(name[0].toUpperCase()) : null,
                  ),
                  const SizedBox(width: MakoloSpacing.sm),
                  Expanded(
                    child: Text(
                      name,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.labelLarge,
                    ),
                  ),
                  if (navigable)
                    Tooltip(
                      message: 'Appui long : aperçu du porteur',
                      child: Icon(
                        Icons.chevron_right_rounded,
                        size: 17,
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                ],
              ),
            ),
          ),
        if (followTarget != null)
          MakoloFollowIconButton(
            key: const Key('discover-owner-follow'),
            followed: followed,
            busy: _followingBusy,
            onPressed: _toggleFollow,
          ),
        if (item.wire['date'] is Map &&
            (item.wire['date'] as Map)['kind'] == 'added_at') ...[
          if (hasOwner) const SizedBox(width: MakoloSpacing.sm),
          Flexible(
            child: Align(
              alignment: Alignment.centerRight,
              child: _dateLabel(context),
            ),
          ),
        ],
      ],
    );
  }

  Widget _dateLabel(BuildContext context) {
    final date = item.wire['date'];
    if (date is! Map || date['kind'] != 'added_at') {
      return const SizedBox.shrink();
    }
    final raw = date['value'];
    if (raw is! String) return const SizedBox.shrink();
    final parsed = DateTime.tryParse(raw);
    if (parsed == null) return const SizedBox.shrink();
    final local = parsed.toLocal();
    final material = MaterialLocalizations.of(context);
    final isFrench = Localizations.localeOf(context).languageCode == 'fr';
    final formatted = material.formatMediumDate(local);
    final relative = discoveryAddedAtLabel(
      local,
      DateTime.now(),
      french: isFrench,
    );
    final label = relative.isNotEmpty ? relative : formatted;
    final exact =
        '$formatted · ${material.formatTimeOfDay(TimeOfDay.fromDateTime(local))}';
    return Tooltip(
      message: '${isFrench ? 'Ajouté le' : 'Added'} $exact',
      child: Semantics(
        label: '${isFrench ? 'Ajouté le' : 'Added'} $exact',
        child: Text(
          label,
          maxLines: 2,
          softWrap: true,
          textAlign: TextAlign.end,
          style: Theme.of(context).textTheme.labelSmall
              ?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant),
        ),
      ),
    );
  }

  bool get _canStartService {
    final handoff = item.engagement;
    final presentation = handoff?['presentation'];
    final caps = handoff?['capabilities'];
    final resource = handoff?['resource'];
    return item.family == 'service_activity' &&
        presentation is Map &&
        presentation['capability'] == 'start' &&
        caps is List &&
        ((presentation['enabled'] == true && caps.contains('start')) ||
            (presentation['requires_auth'] == true &&
                caps.contains('start_after_auth'))) &&
        resource is Map &&
        resource['kind'] == 'service' &&
        resource['id'] is String;
  }

  String? get _nativeTicketChoices {
    final handoff = item.engagement;
    final caps = handoff?['capabilities'];
    final links = handoff?['links'];
    final resource = handoff?['resource'];
    final native = links is Map ? links['native'] : null;
    if (item.family != 'activity' ||
        handoff?['owner'] != 'events' ||
        handoff?['state'] != 'owner_api' ||
        caps is! List ||
        !caps.contains('inspect_offers') ||
        resource is! Map ||
        resource['kind'] != 'event' ||
        native is! String ||
        !native.startsWith('/events/') ||
        !native.endsWith('/tickets') ||
        (resource['slug'] is String &&
            native != '/events/${resource['slug']}/tickets')) {
      return null;
    }
    return native;
  }

  Map<String, dynamic>? get _serverPrimaryAction {
    final value = item.engagement?['primary_action'];
    if (value is! Map) return null;
    return Map<String, dynamic>.from(value);
  }

  String? get _primaryNativePath {
    if (!widget.allowOwnerActions) return null;
    final action = _serverPrimaryAction;
    final destination = action?['destination'];
    if (destination is! Map || destination['kind'] != 'native') return null;
    final path = destination['path'];
    if (path is! String ||
        !path.startsWith('/') ||
        path.contains('?') ||
        path.contains('#') ||
        path.contains('..')) {
      return null;
    }
    final code = action?['code'];
    // The owner-verified contract selects the action. Restrict navigation to
    // the owner-backed native routes supported by this client.
    if (item.engagement?['state'] == 'owner_api' &&
        item.engagement?['owner'] == 'commerce') {
      final caps = item.engagement?['capabilities'];
      final resource = item.engagement?['resource'];
      if (caps is List && resource is Map && resource['id'] is String) {
        final id = resource['id'] as String;
        if (code == 'inspect_offers' &&
            caps.contains('inspect_offers') &&
            resource['kind'] == 'activity' &&
            path == '/commerce/activities/$id/checkout') {
          return path;
        }
        if (code == 'checkout' &&
            caps.contains('checkout') &&
            resource['kind'] == 'journey' &&
            path == '/commerce/journeys/$id/checkout') {
          return path;
        }
        if (code == 'resume_order' &&
            caps.contains('resume_order') &&
            resource['kind'] == 'commerce_order' &&
            path == '/commerce/orders/$id') {
          return path;
        }
      }
    }
    if (code == 'continue' &&
        item.engagement?['state'] == 'owner_api' &&
        item.engagement?['owner'] == 'journeys') {
      final caps = item.engagement?['capabilities'];
      final resource = item.engagement?['resource'];
      if (caps is List &&
          caps.contains('continue') &&
          resource is Map &&
          resource['kind'] == 'journey' &&
          resource['id'] is String &&
          path == '/journeys/${resource['id']}') {
        return path;
      }
    }
    if (code == 'start' && _canStartService) {
      final service = item.engagement!['resource'] as Map;
      return path == '/services/${service['id']}/start' ? path : null;
    }
    if (code == 'inspect_offers' && path == _nativeTicketChoices) {
      return path;
    }
    if (code == 'contribute' &&
        item.family == 'funding_activity' &&
        item.engagement?['owner'] == 'funding' &&
        item.engagement?['state'] == 'owner_api') {
      final engagement = item.engagement!;
      final caps = engagement['capabilities'];
      final resource = engagement['resource'];
      if (caps is List &&
          caps.contains('contribute') &&
          resource is Map &&
          resource['kind'] == 'funding' &&
          resource['id'] is String &&
          path == '/funding/${resource['id']}/contribute') {
        return path;
      }
    }
    if (code == 'start_journey' &&
        item.family == 'activity' &&
        item.engagement?['owner'] == 'obtention' &&
        item.engagement?['state'] == 'owner_api') {
      final engagement = item.engagement!;
      final caps = engagement['capabilities'];
      final resource = engagement['resource'];
      if (caps is List &&
          caps.contains('start_journey') &&
          resource is Map &&
          resource['kind'] == 'obtention' &&
          resource['id'] is String &&
          path == '/obtention/${resource['id']}/choose') {
        return path;
      }
    }
    return null;
  }

  /// Owner details are read-only links and remain distinct from primary
  /// actions (pay, obtain, contribute, start). The owner authorizes on entry.
  String? get _readOnlyOwnerPath {
    if (!widget.detailMode ||
        widget.onOwnerDepth == null ||
        !const {
          'activity',
          'service_activity',
          'funding_activity',
        }.contains(item.family)) {
      return null;
    }
    final resource = item.identity?['resource'];
    if (resource is! Map ||
        resource['kind'] != 'activity' ||
        resource['id'] != item.id ||
        item.id.isEmpty) {
      return null;
    }
    return '/activities/${Uri.encodeComponent(item.id)}';
  }

  /// A Discovery activity may select one specific Occurrence rather than
  /// merely the parent Activity. Keep this N3 identity, including transport
  /// departures, without fabricating a Journey or booking entitlement.
  String? get _readOnlyOccurrencePath {
    if (!widget.detailMode ||
        widget.onOwnerDepth == null ||
        item.family != 'activity') {
      return null;
    }
    final occurrence = item.identity?['occurrence'];
    final id = item.occurrenceId;
    if (occurrence is! Map ||
        occurrence['kind'] != 'occurrence' ||
        occurrence['id'] != id ||
        id == null ||
        id.trim().isEmpty) {
      return null;
    }
    return '/occurrences/${Uri.encodeComponent(id)}';
  }

  String get _centralActionLabel {
    final native = _primaryNativePath;
    if (native == null) return 'Détails';
    final continuation = item.wire['journey_continuation'];
    if (continuation is Map) {
      final links = continuation['links'];
      final resource = continuation['resource'];
      if (resource is Map &&
          resource['kind'] == 'journey' &&
          resource['id'] is String &&
          links is Map &&
          links['native'] == '/journeys/${resource['id']}' &&
          links['native'] == native &&
          const {'active', 'finished'}.contains(continuation['state'])) {
        return continuation['state'] == 'active'
            ? 'Reprendre ma démarche'
            : 'Voir ma démarche';
      }
    }
    final label = _serverPrimaryAction?['label'];
    if (label is String && label.trim().isNotEmpty) return label.trim();
    return switch (_serverPrimaryAction?['code']) {
      'start' => 'Commencer',
      'checkout' => 'Choisir une offre',
      'inspect_offers' => 'Choisir une offre',
      'resume_order' => 'Ma commande',
      'continue' => 'Continuer',
      'contribute' => 'Contribuer',
      'start_journey' => 'Obtenir',
      _ => 'Voir les billets',
    };
  }

  IconData get _centralActionIcon {
    if (_primaryNativePath == null) return Icons.arrow_forward_rounded;
    return switch (_serverPrimaryAction?['code']) {
      'start' => Icons.play_circle_outline_rounded,
      'checkout' => Icons.shopping_bag_outlined,
      'inspect_offers' =>
        item.engagement?['owner'] == 'commerce'
            ? Icons.shopping_bag_outlined
            : Icons.confirmation_number_outlined,
      'resume_order' => Icons.receipt_long_outlined,
      'continue' => Icons.arrow_forward_rounded,
      'contribute' => Icons.volunteer_activism_outlined,
      'start_journey' => Icons.inventory_2_outlined,
      _ => Icons.confirmation_number_outlined,
    };
  }

  void _centralAction(BuildContext context) {
    final path = _primaryNativePath;
    if (path != null) {
      if (widget.onNativeAction != null) {
        widget.onNativeAction!(path);
      } else {
        context.push(path);
      }
    } else {
      // No Web escape hatch: a missing native journey must be built in Flutter.
      widget.onOpen();
    }
  }

  String get _description {
    final summary = item.summary.trim();
    final raw = item.detailFacts?['description'];
    final detail = raw is String ? raw.trim() : '';
    if (detail.isEmpty || detail == summary) return summary;
    if (summary.isEmpty || detail.contains(summary)) return detail;
    return '$summary\n\n$detail';
  }

  Widget _descriptionBody(BuildContext context) {
    final description = _description;
    if (description.isEmpty) return const SizedBox.shrink();
    return LayoutBuilder(
      builder: (context, constraints) {
        final style = DefaultTextStyle.of(context).style;
        final textDirection = Directionality.of(context);
        final painter = TextPainter(
          text: TextSpan(text: description, style: style),
          maxLines: 3,
          textDirection: textDirection,
          textScaler: MediaQuery.textScalerOf(context),
        )..layout(maxWidth: constraints.maxWidth);
        final expandable = !widget.detailMode && painter.didExceedMaxLines;
        final collapsed = !_expanded && expandable;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Semantics(
              button: expandable,
              label: expandable
                  ? (_expanded
                        ? 'Réduire la description'
                        : 'Développer la description')
                  : null,
              child: InkWell(
                key: const Key('discover-description-tap'),
                onTap: expandable
                    ? () => setState(() => _expanded = !_expanded)
                    : null,
                child: AnimatedSize(
                  duration: MakoloMotion.effective(context, MakoloMotion.short),
                  alignment: Alignment.topCenter,
                  child: Text(
                    description,
                    key: const Key('discover-description-text'),
                    maxLines: collapsed ? 3 : null,
                    overflow: collapsed ? TextOverflow.ellipsis : null,
                  ),
                ),
              ),
            ),
            if (expandable)
              TextButton(
                key: const Key('discover-description-expand'),
                style: TextButton.styleFrom(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  minimumSize: const Size(48, 36),
                  visualDensity: VisualDensity.compact,
                  alignment: Alignment.centerLeft,
                ),
                onPressed: () => setState(() => _expanded = !_expanded),
                child: Text(_expanded ? 'Voir moins' : 'Voir plus'),
              ),
          ],
        );
      },
    );
  }

  bool _canOpenResource(Map<String, String?> resource) {
    final url = _publicImage(resource['url']);
    if (url != null && discoverySafeDestination(Uri.parse(url))) return true;
    return resource['text']?.trim().isNotEmpty ?? false;
  }

  Widget _resourceSection(
    BuildContext context,
    List<Map<String, String?>> resources,
  ) {
    final theme = Theme.of(context);
    final visible = widget.detailMode || _allResources
        ? resources
        : resources.take(2);
    return Padding(
      key: const Key('discover-resources-section'),
      padding: EdgeInsets.symmetric(
        horizontal: widget.detailMode ? 12 : 14,
        vertical: widget.detailMode ? 10 : 8,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Documents et ressources', style: theme.textTheme.titleSmall),
          const SizedBox(height: MakoloSpacing.sm),
          AnimatedSize(
            duration: MakoloMotion.effective(context, MakoloMotion.short),
            alignment: Alignment.topCenter,
            child: Column(
              children: [
                for (final resource in visible)
                  Padding(
                    padding: const EdgeInsets.only(bottom: MakoloSpacing.xs),
                    child: InkWell(
                      onTap: _canOpenResource(resource)
                          ? () => _openResource(resource)
                          : null,
                      borderRadius: BorderRadius.circular(MakoloRadii.small),
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(minHeight: 48),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(
                            vertical: MakoloSpacing.xs,
                          ),
                          child: Row(
                            children: [
                              Icon(
                                _resourceIcon(resource),
                                size: 20,
                                color: theme.colorScheme.onSurfaceVariant,
                              ),
                              const SizedBox(width: MakoloSpacing.sm),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      resource['label'] ?? '',
                                      style: theme.textTheme.bodyMedium
                                          ?.copyWith(
                                            color:
                                                theme.brightness ==
                                                    Brightness.dark
                                                ? const Color(0xFFB6A5FF)
                                                : theme.colorScheme.primary,
                                            fontWeight: FontWeight.w600,
                                          ),
                                    ),
                                    if (resource['text']?.isNotEmpty ?? false)
                                      Text(
                                        resource['text']!,
                                        maxLines: 2,
                                        overflow: TextOverflow.ellipsis,
                                        style: theme.textTheme.bodySmall
                                            ?.copyWith(
                                              color: theme
                                                  .colorScheme
                                                  .onSurfaceVariant,
                                            ),
                                      ),
                                  ],
                                ),
                              ),
                              if (_canOpenResource(resource)) ...[
                                const SizedBox(width: MakoloSpacing.xs),
                                Icon(
                                  Icons.chevron_right,
                                  size: 18,
                                  color: theme.colorScheme.onSurfaceVariant,
                                ),
                              ],
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
          if (!widget.detailMode && resources.length > 2)
            TextButton(
              key: const Key('discover-resources-expand'),
              style: TextButton.styleFrom(
                minimumSize: const Size(48, 44),
                padding: const EdgeInsets.symmetric(horizontal: 4),
                alignment: Alignment.centerLeft,
              ),
              onPressed: () => setState(() => _allResources = !_allResources),
              child: Text(
                _allResources
                    ? 'Voir moins de ressources'
                    : 'Voir les ${resources.length} ressources',
              ),
            ),
        ],
      ),
    );
  }

  Widget _facts(BuildContext context) {
    final facts = _reliableFacts;
    if (facts.isEmpty) return const SizedBox.shrink();
    return LayoutBuilder(
      builder: (context, constraints) {
        const gutter = MakoloSpacing.compact;
        final largeText = MediaQuery.textScalerOf(context).scale(1) > 1.3;
        final twoColumns = !largeText && constraints.maxWidth >= 260;
        final itemWidth = twoColumns
            ? (constraints.maxWidth - gutter) / 2
            : constraints.maxWidth;
        return Wrap(
          spacing: gutter,
          runSpacing: MakoloSpacing.md,
          children: [
            for (final fact in facts)
              SizedBox(
                width: itemWidth,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      fact['label'] as String,
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(height: MakoloSpacing.micro),
                    Text(
                      fact['value'] as String,
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  ],
                ),
              ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final saved = _confirmedSaved ?? (item.savedState == 'saved');
    final canToggle =
        _confirmedSaved == null && (saved ? item.canUnsave : item.canSave);
    final savePhase = _saving
        ? MakoloActionPhase.processing
        : _saveFailed
        ? MakoloActionPhase.failed
        : saved
        ? MakoloActionPhase.confirmed
        : MakoloActionPhase.available;

    final resources = _resourceEntries;
    final actionBar = <Widget>[
      const Divider(height: 1),
      Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: MakoloSpacing.xs,
          vertical: MakoloSpacing.xs,
        ),
        child: Row(
          children: [
            Expanded(
              child: MakoloRoundedActionSlot(
                active: saved,
                phase: savePhase,
                child: IconButton(
                  key: Key(
                    widget.detailMode ? 'discover-save-n2' : 'discover-save-n1',
                  ),
                  onPressed:
                      !_saving &&
                          widget.allowOwnerActions &&
                          ((widget.onSave != null && canToggle) ||
                              (widget.allowSavePrompt &&
                                  widget.onSignIn != null))
                      ? _save
                      : null,
                  tooltip: _saving
                      ? 'Enregistrement…'
                      : _saveFailed
                      ? 'Échec de l’enregistrement. Réessayer'
                      : saved
                      ? (widget.detailMode
                            ? 'Retirer des enregistrements'
                            : 'Enregistré')
                      : 'Enregistrer',
                  icon: MakoloActionFeedback(
                    phase: savePhase,
                    child: DiscoveryOrbitIcon(
                      saved: saved,
                      color: theme.colorScheme.primary,
                    ),
                  ),
                ),
              ),
            ),
            if (!widget.detailMode) ...[
              const SizedBox(width: MakoloSpacing.sm),
              Expanded(
                child: MakoloRoundedActionSlot(
                  child: IconButton(
                    key: const Key('discover-primary-n1'),
                    onPressed: () => _centralAction(context),
                    tooltip: _centralActionLabel,
                    icon: Icon(_centralActionIcon),
                  ),
                ),
              ),
            ],
            const SizedBox(width: MakoloSpacing.sm),
            Expanded(
              child: MakoloRoundedActionSlot(
                child: DiscoveryShareControl(
                  item: item,
                  api: widget.shareApi,
                  authenticated: widget.shareAuthenticated,
                  onSignIn: widget.onSignIn,
                  enabled: !widget.detailMode || widget.allowOwnerActions,
                  iconOnly: true,
                  baseUri: widget.baseUri,
                ),
              ),
            ),
          ],
        ),
      ),
    ];
    return DecoratedBox(
      decoration: widget.detailMode
          ? const BoxDecoration()
          : BoxDecoration(
              border: Border(
                bottom: BorderSide(color: theme.colorScheme.outlineVariant),
              ),
            ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: EdgeInsets.symmetric(
              horizontal: widget.detailMode ? 16 : 14,
              vertical: widget.detailMode ? 12 : 8,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _ownerHeader(context),
                const SizedBox(height: MakoloSpacing.sm),
                InkWell(
                  onTap: widget.detailMode ? null : widget.onOpen,
                  child: Text(
                    item.title,
                    style: widget.detailMode
                        ? theme.textTheme.headlineSmall
                        : theme.textTheme.titleLarge,
                  ),
                ),
                const SizedBox(height: MakoloSpacing.xs),
                Builder(
                  builder: (context) {
                    final vertical =
                        (item.representation?['vertical_label']?.toString() ??
                                '')
                            .trim();
                    final eyebrow = (item.eyebrow ?? '').trim();
                    final subtype = item.presentationFacts
                        .where(
                          (fact) =>
                              fact['code'] == 'type' || fact['label'] == 'Type',
                        )
                        .map((fact) => (fact['value'] ?? '').toString().trim())
                        .firstWhere(
                          (value) => value.isNotEmpty,
                          orElse: () => '',
                        );
                    final labels = <String>[];
                    for (final candidate in [vertical, eyebrow, subtype]) {
                      if (candidate.isNotEmpty &&
                          !labels.any(
                            (label) =>
                                label.toLowerCase() == candidate.toLowerCase(),
                          )) {
                        labels.add(candidate);
                      }
                    }
                    if (labels.isEmpty) return const SizedBox.shrink();
                    final linkColor = theme.brightness == Brightness.dark
                        ? const Color(0xFFB6A5FF)
                        : theme.colorScheme.primary;
                    return Wrap(
                      key: const Key('discover-type-row'),
                      spacing: MakoloSpacing.xs,
                      runSpacing: MakoloSpacing.xs,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        for (var i = 0; i < labels.length; i++) ...[
                          if (i > 0)
                            Text('·', style: theme.textTheme.labelMedium),
                          Text(
                            labels[i],
                            style: theme.textTheme.labelMedium?.copyWith(
                              color: i == 0
                                  ? linkColor
                                  : theme.colorScheme.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ],
                    );
                  },
                ),
                if (_description.isNotEmpty) ...[
                  const SizedBox(height: MakoloSpacing.sm),
                  _descriptionBody(context),
                ],

                if (_reliableFacts.isNotEmpty ||
                    (!widget.detailMode && _contextNotes.isNotEmpty)) ...[
                  const SizedBox(height: MakoloSpacing.sm),
                  Padding(
                    key: const Key('discover-facts-section'),
                    padding: const EdgeInsets.symmetric(
                      vertical: MakoloSpacing.xs,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Informations pratiques',
                          style: theme.textTheme.titleSmall,
                        ),
                        const SizedBox(height: MakoloSpacing.sm),
                        if (_reliableFacts.isNotEmpty) _facts(context),
                        for (final note
                            in widget.detailMode
                                ? const <String>[]
                                : _contextNotes)
                          Padding(
                            padding: const EdgeInsets.only(
                              top: MakoloSpacing.xs,
                            ),
                            child: Text(
                              note,
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: theme.colorScheme.onSurfaceVariant,
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),
          if (widget.detailMode &&
              !widget.allowOwnerActions &&
              !widget.collectiveReadOnly)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
              child: Text(
                'Informations conservées. Une connexion et une '
                'vérification sont nécessaires pour agir.',
                style: theme.textTheme.bodySmall,
              ),
            ),
          if (widget.detailMode &&
              widget.allowOwnerActions &&
              !widget.collectiveReadOnly &&
              _primaryNativePath != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
              child: FilledButton.icon(
                key: const Key('discover-primary-n2'),
                onPressed: () => _centralAction(context),
                icon: Icon(_centralActionIcon),
                label: Text(_centralActionLabel),
              ),
            ),
          if (_readOnlyOwnerPath != null || _readOnlyOccurrencePath != null)
            Padding(
              key: const Key('discover-n2-owner-depths'),
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
              child: Wrap(
                spacing: MakoloSpacing.sm,
                runSpacing: MakoloSpacing.xs,
                children: [
                  if (_readOnlyOccurrencePath != null)
                    OutlinedButton.icon(
                      key: const Key('discover-owner-occurrence-n3'),
                      onPressed: () =>
                          widget.onOwnerDepth!(_readOnlyOccurrencePath!),
                      icon: const Icon(Icons.event_available_outlined),
                      label: Text(
                        item.routeLabel == null
                            ? 'Voir cette réalisation'
                            : 'Voir ce départ',
                      ),
                    ),
                  if (_readOnlyOwnerPath != null)
                    OutlinedButton.icon(
                      key: const Key('discover-owner-n3'),
                      onPressed: () =>
                          widget.onOwnerDepth!(_readOnlyOwnerPath!),
                      icon: const Icon(Icons.open_in_new_rounded),
                      label: const Text('Voir l’activité'),
                    ),
                ],
              ),
            ),
          if (widget.detailMode && !widget.collectiveReadOnly) ...actionBar,
          if (widget.detailMode)
            DiscoveryN2DepthSection(
              item: item,
              onOpenOccurrence: widget.onOwnerDepth == null
                  ? null
                  : (id) => widget.onOwnerDepth!(
                      '/occurrences/${Uri.encodeComponent(id)}',
                    ),
            ),
          _media(context),
          if (resources.isNotEmpty) _resourceSection(context, resources),
          if (!widget.detailMode) ...actionBar,
          if (widget.onSelect != null)
            TextButton.icon(
              key: ValueKey('discover-map-action-${widget.item.candidateKey}'),
              onPressed: widget.onSelect,
              icon: const Icon(Icons.map_outlined),
              label: Text(widget.selectionActionLabel ?? 'Voir sur la carte'),
            ),
          if (!widget.detailMode)
            Container(height: 6, color: theme.colorScheme.surfaceContainerLow),
        ],
      ),
    );
  }
}
