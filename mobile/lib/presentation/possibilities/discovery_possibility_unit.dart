import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../../design/makolo_theme.dart';
import '../../network/makolo_api_client.dart';
import '../../features/discovery/discovery_share_sheet.dart';
import '../../features/discovery/discovery_selector.dart';

/// The existing Discovery projection rendered as one N1 unit.
/// Facts and actions remain owned by the server; this widget only composes.
class DiscoveryOrbitIcon extends StatelessWidget {
  const DiscoveryOrbitIcon({
    super.key,
    required this.saved,
    required this.color,
  });

  final bool saved;
  final Color color;

  static const _orbitAvailable = '''
<svg viewBox="0 0 24 24"><path d="M5.2 17.6A8.7 8.7 0 0 1 16.9 5.1" fill="none" stroke="#000" stroke-width="2.2" stroke-linecap="round"/><path d="M18.4 7.2a8.6 8.6 0 0 1 .2 7.4" fill="none" stroke="#000" stroke-width="2.2" stroke-linecap="round"/><circle cx="19.3" cy="17.6" r="1.45" fill="#000"/></svg>
''';
  static const _orbitSaved = '''
<svg viewBox="0 0 24 24"><path d="M5.6 17.2a8.2 8.2 0 1 1 12.9-1.4" fill="none" stroke="#000" stroke-width="2.4" stroke-linecap="round"/><circle cx="12" cy="12" r="3.2" fill="#000"/><circle cx="19.2" cy="17.5" r="1.55" fill="#000"/></svg>
''';

  @override
  Widget build(BuildContext context) {
    return SvgPicture.string(
      saved ? _orbitSaved : _orbitAvailable,
      width: 21,
      height: 21,
      colorFilter: ColorFilter.mode(color, BlendMode.srcIn),
      semanticsLabel: saved ? 'Enregistré' : 'Enregistrer',
    );
  }
}

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

  List<String> get _resourceLabels {
    final labels = <String>[];
    final resources = item.wire['resources'];
    if (resources is List) {
      for (final raw in resources) {
        if (raw is! Map) continue;
        final title = (raw['title'] ?? '').toString().trim();
        if (title.isEmpty) continue;
        final mime = (raw['mime_type'] ?? '').toString().toLowerCase();
        final format = mime.contains('pdf')
            ? 'PDF'
            : mime.contains('spreadsheet') || mime.contains('excel')
            ? 'Tableur'
            : mime.startsWith('video/')
            ? 'Vidéo'
            : mime.startsWith('audio/')
            ? 'Audio'
            : raw['kind'] == 'file'
            ? 'Document'
            : 'Source';
        labels.add('$format · $title');
      }
    }
    for (final binding in item.mediaBindings) {
      final resource = binding['resource'];
      if (resource is! Map) continue;
      final mime = (resource['mime_type'] ?? binding['mime_type'] ?? '')
          .toString()
          .toLowerCase();
      final name = (resource['name'] ?? resource['title'] ?? '')
          .toString()
          .trim();
      final format = mime.contains('pdf')
          ? 'PDF'
          : mime.contains('spreadsheet') || mime.contains('excel')
          ? 'Tableur'
          : mime.startsWith('video/')
          ? 'Vidéo'
          : mime.startsWith('audio/')
          ? 'Audio'
          : mime.contains('document')
          ? 'Document'
          : null;
      if (format != null) labels.add(name.isEmpty ? format : '$format · $name');
    }
    return labels;
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
    final urls = <String>[];
    final seen = <String>{};
    void add(String? source) {
      final url = _publicImage(source);
      if (url != null && seen.add(url)) urls.add(url);
    }

    add(item.imageUrl);
    for (final binding in item.mediaBindings) {
      final resource = binding['resource'];
      if (resource is! Map) continue;
      final mime = (resource['mime_type'] ?? '').toString();
      final purpose = (binding['purpose'] ?? '').toString();
      if (mime.startsWith('image/') || purpose == 'RECOGNIZE') {
        add(resource['url']?.toString());
      }
    }
    if (urls.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final url in urls)
          AspectRatio(
            aspectRatio: 4 / 3,
            child: Image.network(
              url,
              fit: BoxFit.cover,
              semanticLabel: 'Visuel de ${item.title}',
              errorBuilder: (_, _, _) => const SizedBox.shrink(),
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
      onTap: navigable ? () => context.push(nativePath as String) : null,
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
          if (navigable) const Icon(Icons.open_in_new_rounded, size: 16),
        ],
      ),
    );
  }

  Widget _dateLabel(BuildContext context) {
    final date = item.wire['date'];
    if (date is! Map) return const SizedBox.shrink();
    final raw = date['value'];
    final label = date['label'];
    if (raw is! String || label is! String) return const SizedBox.shrink();
    final parsed = DateTime.tryParse(raw);
    if (parsed == null) return const SizedBox.shrink();
    return Text(
      '$label ${MaterialLocalizations.of(context).formatMediumDate(parsed.toLocal())}',
      style: Theme.of(context).textTheme.labelSmall
          ?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant),
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

    final resources = _resourceLabels;
    return DecoratedBox(
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(color: theme.colorScheme.outlineVariant),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (!widget.compact) _media(context),
          InkWell(
            onTap: widget.onOpen,
            child: Padding(
              padding: EdgeInsets.all(
                widget.compact ? MakoloSpacing.sm : MakoloSpacing.md,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.title,
                    style: widget.compact
                        ? theme.textTheme.titleMedium
                        : theme.textTheme.headlineSmall,
                  ),
                  const SizedBox(height: MakoloSpacing.sm),
                  _ownerHeader(context),
                  const SizedBox(height: MakoloSpacing.xs),
                  Text(
                    item.representation?['vertical_label']?.toString() ??
                        item.eyebrow ??
                        '',
                    style: theme.textTheme.labelMedium?.copyWith(
                      color: theme.colorScheme.primary,
                    ),
                  ),
                  _dateLabel(context),
                  if (item.summary.trim().isNotEmpty) ...[
                    const SizedBox(height: MakoloSpacing.sm),
                    Text(
                      item.summary,
                      style: widget.compact
                          ? theme.textTheme.bodySmall
                          : theme.textTheme.bodyMedium,
                    ),
                  ],
                  if (item.detailFacts?['description'] is String &&
                      (item.detailFacts!['description'] as String)
                          .trim()
                          .isNotEmpty &&
                      item.detailFacts!['description'] != item.summary) ...[
                    const SizedBox(height: MakoloSpacing.sm),
                    Text(item.detailFacts!['description'] as String),
                  ],
                  if (item.participantPresentation?['label'] is String &&
                      (item.participantPresentation!['label'] as String)
                          .isNotEmpty) ...[
                    const SizedBox(height: MakoloSpacing.sm),
                    Text(
                      item.participantPresentation!['label'] as String,
                      style: theme.textTheme.labelMedium,
                    ),
                  ],
                  if (resources.isNotEmpty) ...[
                    const SizedBox(height: MakoloSpacing.sm),
                    for (final resource in resources)
                      Padding(
                        padding: const EdgeInsets.only(
                          bottom: MakoloSpacing.xs,
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.description_outlined, size: 18),
                            const SizedBox(width: MakoloSpacing.xs),
                            Expanded(
                              child: Text(
                                resource,
                                style: theme.textTheme.bodySmall,
                              ),
                            ),
                          ],
                        ),
                      ),
                  ],
                  const SizedBox(height: MakoloSpacing.md),
                  _facts(context),
                  _knowledge(context),
                  if (item.variants.isNotEmpty ||
                      item.relations.isNotEmpty) ...[
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
          ),
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
                          : 'Voir plus',
                      icon: Icon(
                        _canStartService
                            ? Icons.play_circle_outline_rounded
                            : _nativeTicketChoices != null
                            ? Icons.confirmation_number_outlined
                            : Icons.open_in_new_rounded,
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
        ],
      ),
    );
  }
}
