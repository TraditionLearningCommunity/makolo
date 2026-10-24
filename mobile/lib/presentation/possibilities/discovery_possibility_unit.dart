import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../design/makolo_theme.dart';
import '../../network/makolo_api_client.dart';
import '../../features/discovery/discovery_share_sheet.dart';
import '../../features/discovery/discovery_selector.dart';
import 'discovery_reader.dart';
import 'discovery_save_icon.dart';

export 'discovery_save_icon.dart' show DiscoveryOrbitIcon;

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
    this.compact = false,
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
  final bool compact;

  @override
  State<DiscoveryPossibilityUnit> createState() =>
      _DiscoveryPossibilityUnitState();
}

class _DiscoveryPossibilityUnitState extends State<DiscoveryPossibilityUnit> {
  bool _saving = false;
  bool _expanded = false;
  int _galleryPage = 0;
  bool _allResources = false;
  bool? _confirmedSaved;

  @override
  void didUpdateWidget(covariant DiscoveryPossibilityUnit oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.item.candidateKey != widget.item.candidateKey ||
        (_confirmedSaved != null &&
            widget.item.savedState ==
                (_confirmedSaved! ? 'saved' : 'not_saved'))) {
      _confirmedSaved = null;
    }
    if (oldWidget.item.candidateKey != widget.item.candidateKey) {
      _expanded = false;
      _galleryPage = 0;
      _allResources = false;
    }
  }

  Future<void> _save() async {
    if (_saving || widget.onSave == null) return;
    final previousState = widget.item.savedState;
    setState(() => _saving = true);
    try {
      await widget.onSave!();
      if (mounted &&
          !widget.allowSavePrompt &&
          widget.item.savedState == previousState) {
        setState(() => _confirmedSaved = previousState != 'saved');
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('L’enregistrement n’a pas pu être confirmé.'),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  DiscoveryItemPresentation get item => widget.item;

  List<Map<String, dynamic>> get _reliableFacts {
    final facts = <Map<String, dynamic>>[];
    final seen = <String>{};

    void add(String code, String label, String? value) {
      if (value == null || value.trim().isEmpty || !seen.add(code)) return;
      facts.add({'code': code, 'label': label, 'value': value});
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
    add('capacity', 'Disponibilité', item.availability);
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
      if (kind.startsWith('start_') && seen.contains('when')) continue;
      if (label != null) add(kind, label, fact['value']?.toString());
    }
    for (final fact in item.spatialFacts) {
      final role = fact['role']?.toString() ?? '';
      if (role == 'primary' && seen.contains('place')) continue;
      final place = fact['place'];
      if (place is Map) {
        add(
          'place_$role',
          role.isEmpty ? 'Lieu' : role,
          place['name']?.toString(),
        );
      }
    }
    return facts;
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
        builder: (_) => DiscoveryReader(items: items, initialIndex: index),
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
    final seen = <String>{};
    void add(String? source, String label) {
      final url = _publicImage(source);
      if (url != null && seen.add(url)) {
        images.add({'url': url, 'label': label});
      }
    }

    add(item.imageUrl, 'Visuel de ${item.title}');
    for (final binding in item.mediaBindings) {
      final resource = binding['resource'];
      if (resource is! Map) continue;
      final mime = (resource['mime_type'] ?? '').toString().toLowerCase();
      if (!mime.startsWith('image/')) continue;
      add(
        resource['url']?.toString(),
        (resource['alt_text'] ?? 'Visuel de ${item.title}').toString(),
      );
    }
    if (images.isEmpty) return const SizedBox.shrink();
    if (images.length == 1) {
      final image = images.first;
      return InkWell(
        onTap: () => _openReader([
          DiscoveryReaderItem(
            title: image['label']!,
            uri: Uri.parse(image['url']!),
            mimeType: 'image/png',
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
                      mimeType: 'image/png',
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
    if (name == null || name.isEmpty) return const SizedBox.shrink();
    final owner = item.ownerFacts;
    final representation = owner?['representation'];
    final ownerLinks = owner?['links'];
    final avatar = representation is Map
        ? _publicImage(representation['avatar_url']?.toString())
        : null;
    final nativePath = ownerLinks is Map ? ownerLinks['native'] : null;
    final navigable =
        owner?['capabilities'] is List &&
        (owner!['capabilities'] as List).contains('view_public') &&
        nativePath is String &&
        (nativePath.startsWith('/spaces/') ||
            nativePath.startsWith('/people/'));
    return InkWell(
      onTap: navigable ? () => context.push(nativePath) : null,
      child: Row(
        children: [
          CircleAvatar(
            radius: 19,
            foregroundImage: avatar == null ? null : NetworkImage(avatar),
            child: avatar == null ? Text(name[0].toUpperCase()) : null,
          ),
          const SizedBox(width: MakoloSpacing.sm),
          Expanded(
            child: Text(name, style: Theme.of(context).textTheme.labelLarge),
          ),
        ],
      ),
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
    final now = DateTime.now();
    final elapsed = now.difference(local);
    final calendarDays = DateTime(now.year, now.month, now.day)
        .difference(DateTime(local.year, local.month, local.day)).inDays;
    final material = MaterialLocalizations.of(context);
    final isFrench = Localizations.localeOf(context).languageCode == 'fr';
    final exact = '${material.formatMediumDate(local)} · '
        '${material.formatTimeOfDay(TimeOfDay.fromDateTime(local))}';
    String relative;
    if (elapsed.isNegative || elapsed.inMinutes < 1) {
      relative = isFrench ? 'à l’instant' : 'just now';
    } else if (elapsed.inHours < 1) {
      relative = isFrench
          ? 'il y a ${elapsed.inMinutes} min'
          : '${elapsed.inMinutes} min ago';
    } else if (calendarDays == 0) {
      relative = isFrench
          ? 'il y a ${elapsed.inHours} h'
          : '${elapsed.inHours} h ago';
    } else if (calendarDays == 1) {
      relative = isFrench ? 'hier' : 'yesterday';
    } else if (calendarDays < 7) {
      relative = isFrench
          ? 'il y a $calendarDays jours'
          : '$calendarDays days ago';
    } else if (calendarDays < 35) {
      final weeks = calendarDays ~/ 7;
      relative = isFrench
          ? 'il y a $weeks semaine${weeks > 1 ? 's' : ''}'
          : '$weeks week${weeks > 1 ? 's' : ''} ago';
    } else {
      relative = material.formatMediumDate(local);
    }
    return Tooltip(
      message: exact,
      child: Semantics(
        label: '${isFrench ? 'Ajouté' : 'Added'} $relative, $exact',
        child: Text(
          relative,
          textAlign: TextAlign.end,
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
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
        presentation['enabled'] == true &&
        caps is List &&
        caps.contains('start') &&
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
        caps is! List ||
        !caps.contains('inspect_offers') ||
        resource is! Map ||
        resource['kind'] != 'event' ||
        native is! String ||
        !native.startsWith('/events/') ||
        !native.endsWith('/tickets')) {
      return null;
    }
    return native;
  }

  void _centralAction(BuildContext context) {
    if (_canStartService) {
      final service = item.engagement!['resource'] as Map;
      context.push('/services/${service['id']}/start');
    } else if (_nativeTicketChoices != null) {
      context.push(_nativeTicketChoices!);
    } else {
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
        final expandable = painter.didExceedMaxLines;
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
                child: Text(
                  description,
                  key: const Key('discover-description-text'),
                  maxLines: collapsed ? 3 : null,
                  overflow: collapsed ? TextOverflow.ellipsis : null,
                ),
              ),
            ),
            if (expandable)
              TextButton(
                key: const Key('discover-description-expand'),
                style: TextButton.styleFrom(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  minimumSize: const Size(48, 44),
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

  Widget _facts(BuildContext context) {
    final facts = _reliableFacts;
    if (facts.isEmpty) return const SizedBox.shrink();
    return Wrap(
      spacing: MakoloSpacing.md,
      runSpacing: MakoloSpacing.sm,
      children: [
        for (final fact in facts)
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 180),
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
                Text(
                  fact['value'] as String,
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ],
            ),
          ),
      ],
    );
  }

  Widget _knowledge(BuildContext context) {
    final significant = item.assessment
        .where((fact) {
          return fact['state'] == 'favorable' ||
              fact['state'] == 'limiting' ||
              fact['state'] == 'unknown';
        })
        .take(3);
    if (significant.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final fact in significant)
          if (fact['label'] is String && (fact['label'] as String).isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: MakoloSpacing.xs),
              child: Text(
                fact['label'] as String,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final saved = _confirmedSaved ?? (item.savedState == 'saved');
    final canToggle =
        _confirmedSaved == null && (saved ? item.canUnsave : item.canSave);

    final resources = _resourceEntries;
    return DecoratedBox(
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(color: theme.colorScheme.outlineVariant),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _ownerHeader(context),
                const SizedBox(height: MakoloSpacing.sm),
                InkWell(
                  onTap: widget.onOpen,
                  child: Text(item.title, style: theme.textTheme.titleLarge),
                ),
                const SizedBox(height: MakoloSpacing.xs),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if ((item.representation?['vertical_label']
                                      ?.toString() ??
                                  item.eyebrow ??
                                  '')
                              .trim()
                              .isNotEmpty)
                            Text(
                              item.representation?['vertical_label']
                                      ?.toString() ??
                                  item.eyebrow ??
                                  '',
                              style: theme.textTheme.labelMedium?.copyWith(
                                color: theme.colorScheme.primary,
                              ),
                            ),
                          if (item.participantPresentation?['label']
                                  is String &&
                              (item.participantPresentation!['label']
                                      as String)
                                  .trim()
                                  .isNotEmpty &&
                              item.participantPresentation!['label'] !=
                                  item.representation?['vertical_label'] &&
                              item.participantPresentation!['label'] !=
                                  item.eyebrow)
                            Text(
                              item.participantPresentation!['label'] as String,
                              style: theme.textTheme.labelMedium?.copyWith(
                                color: theme.colorScheme.onSurfaceVariant,
                              ),
                            ),
                        ],
                      ),
                    ),
                    const SizedBox(width: MakoloSpacing.sm),
                    Flexible(child: _dateLabel(context)),
                  ],
                ),
                const SizedBox(height: MakoloSpacing.sm),
                if (_reliableFacts.isNotEmpty && !_expanded)
                  Wrap(
                    spacing: MakoloSpacing.sm,
                    runSpacing: MakoloSpacing.xs,
                    children: [
                      for (final fact in _reliableFacts)
                        Text(
                          fact['value'] as String,
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                    ],
                  ),
                if (_expanded) ...[
                  if (_reliableFacts.isNotEmpty)
                    const SizedBox(height: MakoloSpacing.sm),
                  _facts(context),
                  _knowledge(context),
                ],
                if (_description.isNotEmpty) ...[
                  const SizedBox(height: MakoloSpacing.sm),
                  _descriptionBody(context),
                ],
                if (resources.isNotEmpty) ...[
                  const SizedBox(height: MakoloSpacing.sm),
                  for (final resource in (_allResources ? resources : resources.take(3)))
                    Padding(
                      padding: const EdgeInsets.only(bottom: MakoloSpacing.xs),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(_resourceIcon(resource), size: 18),
                              const SizedBox(width: MakoloSpacing.xs),
                              Expanded(
                                child: InkWell(
                                  onTap: () => _openResource(resource),
                                  child: Padding(
                                    padding: const EdgeInsets.symmetric(
                                      vertical: MakoloSpacing.xs,
                                    ),
                                    child: Text(
                                      resource['label'] ?? '',
                                      style: theme.textTheme.bodySmall
                                          ?.copyWith(
                                            color: theme.colorScheme.primary,
                                            fontWeight: FontWeight.w600,
                                          ),
                                    ),
                                  ),
                                ),
                              ),
                            ],
                          ),
                          if (resource['text']?.isNotEmpty ?? false)
                            Padding(
                              padding: const EdgeInsets.only(
                                left: 26,
                                top: MakoloSpacing.xs,
                              ),
                              child: InkWell(
                                onTap: () => _openResource(resource),
                                child: Text(
                                  resource['text']!.length > 180
                                      ? "${resource['text']!.substring(0, 180)}…"
                                      : resource['text']!,
                                  style: theme.textTheme.bodySmall,
                                ),
                              ),
                            ),
                        ],
                      ),
                    ),
                  if (resources.length > 3)
                    TextButton(
                      key: const Key('discover-resources-expand'),
                      onPressed: () =>
                          setState(() => _allResources = !_allResources),
                      child: Text(
                        _allResources
                            ? 'Voir moins de ressources'
                            : 'Voir les ${resources.length} ressources',
                      ),
                    ),
                ],
                if (item.variants.isNotEmpty || item.relations.isNotEmpty) ...[
                  const SizedBox(height: MakoloSpacing.sm),
                  Text(
                    [
                      if (item.variants.isNotEmpty)
                        '${item.variants.length} variantes',
                      if (item.relations.isNotEmpty)
                        '${item.relations.length} relations',
                    ].join(' · '),
                    style: theme.textTheme.bodySmall,
                  ),
                ],
              ],
            ),
          ),
          _media(context),
          ...[
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: MakoloSpacing.xs,
                vertical: MakoloSpacing.xs,
              ),
              child: Row(
                children: [
                  Expanded(
                    child: IconButton(
                      key: const Key('discover-save-n1'),
                      onPressed:
                          !_saving &&
                              widget.onSave != null &&
                              (canToggle || widget.allowSavePrompt)
                          ? _save
                          : null,
                      tooltip: _saving
                          ? 'Enregistrement…'
                          : saved
                          ? 'Enregistré'
                          : 'Enregistrer',
                      icon: DiscoveryOrbitIcon(
                        saved: saved,
                        color: theme.colorScheme.primary,
                      ),
                    ),
                  ),
                  Expanded(
                    child: IconButton(
                      key: const Key('discover-primary-n1'),
                      onPressed: () => _centralAction(context),
                      tooltip: _canStartService
                          ? 'Commencer'
                          : _nativeTicketChoices != null
                          ? 'Voir les billets'
                          : 'Consulter dans Makolo',
                      icon: Icon(
                        _canStartService
                            ? Icons.play_circle_outline_rounded
                            : _nativeTicketChoices != null
                            ? Icons.confirmation_number_outlined
                            : Icons.arrow_forward_rounded,
                      ),
                    ),
                  ),
                  Expanded(
                    child: DiscoveryShareControl(
                      item: item,
                      api: widget.shareApi,
                      authenticated: widget.shareAuthenticated,
                      onSignIn: widget.onSignIn,
                      iconOnly: true,
                      baseUri: widget.baseUri,
                    ),
                  ),
                ],
              ),
            ),
          ],
          if (widget.onSelect != null)
            TextButton.icon(
              key: ValueKey('discover-map-action-${widget.item.candidateKey}'),
              onPressed: widget.onSelect,
              icon: const Icon(Icons.map_outlined),
              label: Text(widget.selectionActionLabel ?? 'Voir sur la carte'),
            ),
          Container(height: 10, color: theme.colorScheme.surfaceContainerLow),
        ],
      ),
    );
  }
}
