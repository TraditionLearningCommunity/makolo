import 'dart:async';

import 'package:flutter/material.dart';

import '../../platform/preferences/secure_string_preferences.dart';

import '../../data/local/profile_store.dart';
import '../../design/identity_surface.dart';
import '../../navigation/destination.dart';
import '../../presentation/possibilities/discovery_save_icon.dart';
import '../../sync/owner_source_state.dart';
import 'me_selector.dart';

/// Moi is a compact personal index. Domain facts remain in their owner depths.
class MeHub extends StatefulWidget {
  const MeHub({
    super.key,
    required this.selection,
    required this.profileId,
    this.store,
    required this.onSelectItem,
    required this.canNavigate,
  });

  final MeSelection selection;
  final String? profileId;
  final ProfileStore? store;
  final ValueChanged<MeItemPresentation> onSelectItem;
  final bool canNavigate;

  @override
  State<MeHub> createState() => _MeHubState();
}

class _MeHubState extends State<MeHub> {
  static const _storage = SecureStringPreferences();
  MakoloTerritoryLayout _layout = MakoloTerritoryLayout.list;
  StreamSubscription<List<StoredProjection>>? _accessSubscription;
  StreamSubscription<List<StoredProjection>>? _historySubscription;
  StreamSubscription<OwnerSourceState>? _accessSourceSubscription;
  StreamSubscription<OwnerSourceState>? _historySourceSubscription;
  bool _accessInvalidated = false;
  bool _historyInvalidated = false;
  List<MeItemPresentation> _accessPreviews = const [];
  List<MeItemPresentation> _historyPreviews = const [];

  String? get _storageKey {
    final id = widget.profileId;
    return id == null || id.isEmpty ? null : 'me.layout.$id';
  }

  @override
  void initState() {
    super.initState();
    _restoreLayout();
    _bindLocalPreviews();
  }

  @override
  void dispose() {
    unawaited(_accessSubscription?.cancel());
    unawaited(_historySubscription?.cancel());
    unawaited(_accessSourceSubscription?.cancel());
    unawaited(_historySourceSubscription?.cancel());
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant MeHub oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.profileId != oldWidget.profileId) {
      _layout = MakoloTerritoryLayout.list;
      _restoreLayout();
    }
    if (widget.store != oldWidget.store ||
        widget.profileId != oldWidget.profileId) {
      unawaited(_accessSubscription?.cancel());
      unawaited(_historySubscription?.cancel());
      unawaited(_accessSourceSubscription?.cancel());
      unawaited(_historySourceSubscription?.cancel());
      _accessPreviews = const [];
      _historyPreviews = const [];
      _accessInvalidated = false;
      _historyInvalidated = false;
      _bindLocalPreviews();
    }
  }

  static Map<String, dynamic>? _asMap(Object? raw) {
    if (raw is! Map) return null;
    return raw.map((key, value) => MapEntry(key.toString(), value));
  }

  static int _offset(StoredProjection page) {
    final payloadPage = _asMap(page.payload['page']);
    final value = payloadPage?['offset'];
    return value is int ? value : 0;
  }

  void _bindLocalPreviews() {
    final store = widget.store;
    if (store == null) return;
    _accessSourceSubscription =
        watchOwnerSourceState(
          database: store.database,
          profileId: store.profileId,
          sourceKey: 'accesses:beneficiary:0:24',
        ).listen((state) {
          if (mounted && widget.store == store) {
            setState(() => _accessInvalidated = state.invalidated);
          }
        });
    _historySourceSubscription =
        watchOwnerSourceState(
          database: store.database,
          profileId: store.profileId,
          sourceKey: 'history:0:24',
        ).listen((state) {
          if (mounted && widget.store == store) {
            setState(() => _historyInvalidated = state.invalidated);
          }
        });
    _accessSubscription = store.watchProjections('personal.accesses').listen((
      pages,
    ) {
      if (!mounted || store != widget.store) return;
      final preview = <MeItemPresentation>[];
      final seen = <String>{};
      final ordered =
          pages
              .where((page) => page.resourceKey.startsWith('beneficiary:'))
              .toList()
            ..sort((a, b) => _offset(a).compareTo(_offset(b)));
      for (final page in ordered) {
        final items = page.payload['items'];
        if (items is! List) continue;
        for (final raw in items) {
          final item = _asMap(raw);
          final identity = _asMap(item?['identity']);
          final activity = _asMap(item?['activity']);
          final id = identity?['id']?.toString();
          final title = activity?['title']?.toString();
          if (id == null || title == null || !seen.add(id)) continue;
          preview.add(
            MeItemPresentation(
              destination: StructuredDestination(kind: 'access', id: id),
              title: title,
              canOpen: true,
            ),
          );
          if (preview.length == 3) break;
        }
        if (preview.length == 3) break;
      }
      setState(() => _accessPreviews = preview);
    });
    _historySubscription = store.watchProjections('personal.history').listen((
      pages,
    ) {
      if (!mounted || store != widget.store) return;
      final preview = <MeItemPresentation>[];
      final seen = <String>{};
      final ordered = pages.toList()
        ..sort((a, b) => _offset(a).compareTo(_offset(b)));
      for (final page in ordered) {
        final items = page.payload['items'];
        if (items is! List) continue;
        for (final raw in items) {
          final item = _asMap(raw);
          final source = _asMap(item?['source']);
          final kind = source?['kind']?.toString();
          final id = source?['id']?.toString();
          final title = item?['title']?.toString();
          if (title == null) continue;
          final key = '$kind:$id:$title';
          if (!seen.add(key)) continue;
          preview.add(
            MeItemPresentation(
              destination: StructuredDestination(
                kind: kind ?? 'history',
                id: id ?? 'unknown',
              ),
              title: title,
              canOpen: id != null && {'journey', 'access'}.contains(kind),
            ),
          );
          if (preview.length == 3) break;
        }
        if (preview.length == 3) break;
      }
      setState(() => _historyPreviews = preview);
    });
  }

  Future<void> _restoreLayout() async {
    final key = _storageKey;
    if (key == null) return;
    try {
      final saved = await _storage.read(key: key);
      if (!mounted || key != _storageKey) return;
      if (saved == 'grid') setState(() => _layout = MakoloTerritoryLayout.grid);
    } on Object {
      // A missing native store never blocks the personal index.
    }
  }

  void _chooseLayout(MakoloTerritoryLayout next) {
    if (_layout == next) return;
    setState(() => _layout = next);
    final key = _storageKey;
    if (key != null) {
      unawaited(_storeLayout(key, next));
    }
  }

  Future<void> _storeLayout(String key, MakoloTerritoryLayout value) async {
    try {
      await _storage.write(
        key: key,
        value: value == MakoloTerritoryLayout.grid ? 'grid' : 'list',
      );
    } on Object {
      // The view stays usable even when a device preference cannot be saved.
    }
  }

  void _open(String kind, String title) {
    if (!widget.canNavigate) return;
    widget.onSelectItem(
      MeItemPresentation(
        destination: StructuredDestination(kind: kind, id: 'mine'),
        title: title,
        canOpen: true,
      ),
    );
  }

  MeTerritorySelection? _territory(String key) {
    for (final territory in widget.selection.territories) {
      if (territory.presentation.key == key) return territory;
    }
    return null;
  }

  List<MeItemPresentation> _fromConsiderations(Set<String> kinds) {
    final territory = _territory('considerations');
    if (territory == null) return const [];
    return territory.items
        .where((item) => kinds.contains(item.destination.kind))
        .toList(growable: false);
  }

  List<_MeEntry> _entries() {
    final interests = _fromConsiderations({'topic', 'open_to'});
    final watches = _fromConsiderations({'watch'});
    final saved = _fromConsiderations({'activity'});
    final followed = _fromConsiderations({'space', 'profile'});
    final collectives = _territory('collectives');
    final resources = _territory('resources');
    final support = _territory('support');
    return [
      _MeEntry(
        kind: 'access_collection',
        title: 'Mes accès',
        subtitle: 'Billets, invitations et droits',
        icon: Icons.confirmation_number_outlined,
        previews: _accessInvalidated ? const [] : _accessPreviews,
      ),
      // The actual preview comes from this Profile's locally retained Access
      // collection; it is never invented from the existence of a link.
      _MeEntry(
        kind: 'considerations',
        title: 'Ce qui compte pour moi',
        subtitle: 'Centres d’intérêt et Ouvert à',
        icon: Icons.interests_outlined,
        previews: interests,
      ),
      _MeEntry(
        kind: 'watches_collection',
        title: 'Mes veilles',
        subtitle: 'Ce que je surveille',
        icon: Icons.notifications_active_outlined,
        previews: watches,
      ),
      _MeEntry(
        kind: 'saved_collection',
        title: 'Mes enregistrements',
        subtitle: 'À retrouver',
        icon: Icons.bookmark_rounded,
        previews: saved,
        count: _territory('considerations')?.savedCount,
      ),
      _MeEntry(
        kind: 'follows_collection',
        title: 'Mes suivis',
        subtitle: 'Personnes et Espaces suivis',
        icon: Icons.person_add_alt_1_outlined,
        previews: followed,
      ),
      _MeEntry(
        kind: 'collectives',
        title: 'Mes collectifs',
        subtitle: 'Espaces, équipes et groupes',
        icon: Icons.groups_outlined,
        previews: collectives?.items ?? const [],
        count: collectives?.totalCount,
      ),
      _MeEntry(
        kind: 'resource_collection',
        title: 'Mes ressources',
        subtitle: 'Documents, preuves et titres',
        icon: Icons.file_copy_outlined,
        previews: (resources?.items ?? const [])
            .where((item) => item.destination.kind != 'resource_collection')
            .toList(growable: false),
        count: resources?.totalCount,
      ),
      if (widget.selection.canOpenHistory)
        _MeEntry(
          kind: 'history',
          title: 'Mon historique',
          subtitle: 'Mon parcours',
          icon: Icons.history_rounded,
          previews: _historyInvalidated ? const [] : _historyPreviews,
        ),
      if (support != null)
        _MeEntry(
          kind: 'support_collection',
          title: 'Mes appuis',
          subtitle: 'Reconnaissance, fidélité et partenaires',
          icon: Icons.handshake_outlined,
          previews: support.items,
        ),
    ];
  }

  Widget _organizerEntry(BuildContext context) => MakoloPrimaryShortcut(
    tapKey: const Key('me-shortcut-organizer'),
    title: 'Mes démarches',
    subtitle: 'Projets, dossiers et démarches',
    icon: Icons.folder_copy_outlined,
    onOpen: widget.canNavigate
        ? () => _open('organizer_collection', 'Mes démarches')
        : null,
  );

  @override
  Widget build(BuildContext context) {
    final entries = _entries();
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _organizerEntry(context),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: Text(
                  'Mon espace',
                  style: Theme.of(context).textTheme.titleMedium
                      ?.copyWith(fontWeight: FontWeight.w800),
                ),
              ),
              MakoloTerritoryViewToggle(
                toggleKey: const Key('me-layout-toggle'),
                value: _layout,
                onChanged: _chooseLayout,
              ),
            ],
          ),
          const SizedBox(height: 8),
          if (_layout == MakoloTerritoryLayout.list)
            Column(
              key: const Key('me-navigation-list'),
              children: [
                for (final entry in entries)
                  _MeHubListEntry(
                    entry: entry,
                    scheme: scheme,
                    canNavigate: widget.canNavigate,
                    onOpen: () => _open(entry.kind, entry.title),
                    onOpenPreview: widget.onSelectItem,
                  ),
              ],
            )
          else
            LayoutBuilder(
              builder: (context, constraints) {
                final twoColumns = constraints.maxWidth >= 320;
                final itemWidth = twoColumns
                    ? (constraints.maxWidth - 12) / 2
                    : constraints.maxWidth;
                return Wrap(
                  key: const Key('me-navigation-grid'),
                  spacing: 10,
                  runSpacing: 10,
                  children: [
                    for (final entry in entries)
                      SizedBox(
                        width: itemWidth,
                        child: _MeHubGridEntry(
                          entry: entry,
                          canNavigate: widget.canNavigate,
                          onOpen: () => _open(entry.kind, entry.title),
                        ),
                      ),
                  ],
                );
              },
            ),
        ],
      ),
    );
  }
}

class _MeEntry {
  const _MeEntry({
    required this.kind,
    required this.title,
    required this.subtitle,
    required this.icon,
    this.previews = const [],
    this.count,
  });

  final String kind;
  final String title;
  final String subtitle;
  final IconData icon;
  final List<MeItemPresentation> previews;
  final int? count;
}

class _MeHubListEntry extends StatelessWidget {
  const _MeHubListEntry({
    required this.entry,
    required this.scheme,
    required this.canNavigate,
    required this.onOpen,
    required this.onOpenPreview,
  });

  final _MeEntry entry;
  final ColorScheme scheme;
  final bool canNavigate;
  final VoidCallback onOpen;
  final ValueChanged<MeItemPresentation> onOpenPreview;

  @override
  Widget build(BuildContext context) => MakoloTerritoryListCard(
    tapKey: Key('me-entry-${entry.kind}'),
    title: entry.title,
    subtitle: entry.subtitle,
    count: entry.count,
    symbol:
        entry.kind == 'follows_collection' &&
            entry.previews.any((item) => item.destination.kind == 'profile')
        ? MakoloPeopleAvatarStack(
            names: [
              for (final item in entry.previews)
                if (item.destination.kind == 'profile') item.title,
            ],
            size: 30,
          )
        : _MeHubSymbol(
            kind: entry.kind,
            fallback: entry.icon,
            size: 24,
            color: scheme.primary,
          ),
    onOpen: canNavigate ? onOpen : null,
    bottomSpacing: 6,
    headerVerticalPadding: 12,
    previewVerticalPadding: 5,
    previews: [
      for (final item in entry.previews.take(3))
        MakoloTerritoryPreview(
          title: item.title,
          onOpen: canNavigate && item.canOpen
              ? () => onOpenPreview(item)
              : null,
        ),
    ],
  );
}

class _MeHubGridEntry extends StatelessWidget {
  const _MeHubGridEntry({
    required this.entry,
    required this.canNavigate,
    required this.onOpen,
  });

  final _MeEntry entry;
  final bool canNavigate;
  final VoidCallback onOpen;

  String? get _countDescription {
    final count = entry.count;
    if (count == null || count <= 0) return null;
    return switch (entry.kind) {
      'saved_collection' =>
        count.toString() + (count == 1 ? ' opportunité' : ' opportunités'),
      'collectives' =>
        count.toString() + (count == 1 ? ' collectif' : ' collectifs'),
      'resource_collection' =>
        count.toString() + (count == 1 ? ' ressource' : ' ressources'),
      _ => null,
    };
  }

  @override
  Widget build(BuildContext context) => MakoloTerritoryGridCard(
    tapKey: Key('me-grid-${entry.kind}'),
    title: entry.title,
    subtitle: entry.subtitle,
    countDescription: _countDescription,
    symbol:
        entry.kind == 'follows_collection' &&
            entry.previews.any((item) => item.destination.kind == 'profile')
        ? MakoloPeopleAvatarStack(
            names: [
              for (final item in entry.previews)
                if (item.destination.kind == 'profile') item.title,
            ],
            size: 32,
          )
        : _MeHubSymbol(
            kind: entry.kind,
            fallback: entry.icon,
            size: 32,
            color: Theme.of(context).colorScheme.primary,
          ),
    onOpen: canNavigate ? onOpen : null,
  );
}

/// Three recognizable owner-domain silhouettes, shared by both view modes.
class _MeHubSymbol extends StatelessWidget {
  const _MeHubSymbol({
    required this.kind,
    required this.fallback,
    required this.size,
    required this.color,
  });

  final String kind;
  final IconData fallback;
  final double size;
  final Color color;

  @override
  Widget build(BuildContext context) {
    if (kind == 'saved_collection') {
      return DiscoveryOrbitIcon(saved: true, color: color, size: size);
    }
    if (kind != 'project_collection' &&
        kind != 'dossier_collection' &&
        kind != 'resource_collection') {
      return Icon(fallback, size: size, color: color);
    }
    return CustomPaint(
      size: Size.square(size),
      painter: _MeDomainSymbolPainter(kind: kind, color: color),
    );
  }
}

class _MeDomainSymbolPainter extends CustomPainter {
  const _MeDomainSymbolPainter({required this.kind, required this.color});

  final String kind;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.scale(size.width / 36, size.height / 36);
    final stroke = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.15
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;

    if (kind == 'project_collection') {
      // One living horizon: a crown, a trunk and visible roots.
      final crown = Path()
        ..moveTo(18, 5)
        ..cubicTo(15, 2, 9, 4, 9, 9)
        ..cubicTo(4, 8, 2, 14, 6, 18)
        ..cubicTo(9, 22, 13, 21, 18, 20)
        ..cubicTo(23, 22, 29, 21, 31, 17)
        ..cubicTo(34, 13, 31, 9, 26, 9)
        ..cubicTo(25, 4, 21, 3, 18, 5)
        ..close();
      canvas.drawPath(crown, stroke);
      canvas.drawLine(const Offset(18, 19), const Offset(18, 29), stroke);
      canvas.drawLine(const Offset(18, 24), const Offset(13, 17), stroke);
      canvas.drawLine(const Offset(18, 23), const Offset(23, 17), stroke);
      canvas.drawLine(const Offset(18, 29), const Offset(10, 33), stroke);
      canvas.drawLine(const Offset(18, 29), const Offset(25, 33), stroke);
      canvas.drawLine(const Offset(18, 30), const Offset(18, 34), stroke);
    } else if (kind == 'dossier_collection') {
      // Papers extend above the folder, so it cannot be mistaken for assets.
      final paper = Path()
        ..moveTo(13, 13)
        ..lineTo(13, 4)
        ..lineTo(24, 4)
        ..lineTo(28, 8)
        ..lineTo(28, 20);
      canvas.drawPath(paper, stroke);
      canvas.drawLine(const Offset(24, 4), const Offset(24, 9), stroke);
      canvas.drawLine(const Offset(24, 9), const Offset(28, 9), stroke);
      canvas.drawLine(const Offset(17, 12), const Offset(24, 12), stroke);
      final folder = Path()
        ..moveTo(3, 13)
        ..lineTo(3, 31)
        ..lineTo(33, 31)
        ..lineTo(33, 15)
        ..lineTo(19, 15)
        ..lineTo(16, 12)
        ..lineTo(3, 12)
        ..close();
      canvas.drawPath(folder, stroke);
      canvas.drawLine(const Offset(8, 22), const Offset(28, 22), stroke);
    } else if (kind == 'resource_collection') {
      // Three independent files, not another folder or project.
      final backFile = Path()
        ..moveTo(5, 12)
        ..lineTo(5, 32)
        ..lineTo(23, 32);
      final middleFile = Path()
        ..moveTo(10, 8)
        ..lineTo(10, 28)
        ..lineTo(28, 28);
      final frontFile = Path()
        ..moveTo(15, 4)
        ..lineTo(27, 4)
        ..lineTo(32, 9)
        ..lineTo(32, 24)
        ..lineTo(15, 24)
        ..close();
      canvas.drawPath(backFile, stroke);
      canvas.drawPath(middleFile, stroke);
      canvas.drawPath(frontFile, stroke);
      canvas.drawLine(const Offset(27, 4), const Offset(27, 9), stroke);
      canvas.drawLine(const Offset(27, 9), const Offset(32, 9), stroke);
      canvas.drawLine(const Offset(19, 14), const Offset(27, 14), stroke);
      canvas.drawLine(const Offset(19, 19), const Offset(27, 19), stroke);
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant _MeDomainSymbolPainter oldDelegate) =>
      oldDelegate.kind != kind || oldDelegate.color != color;
}
