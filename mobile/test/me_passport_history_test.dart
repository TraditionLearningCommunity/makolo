import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/me/me_passport_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

const _versionId = '11111111-1111-4111-8111-111111111111';
const _shareId = '22222222-2222-4222-8222-222222222222';

class _DatedPassportApi implements MakoloApiClient {
  _DatedPassportApi({this.withShares = false});
  final bool withShares;
  bool revoked = false;
  bool shareRevoked = false;
  String? lastPostPath;
  final List<String> postedPaths = [];
  @override
  Uri get baseUri => Uri.parse('https://example.test/');

  ApiResponse _envelope(String projection, Map<String, dynamic> data) =>
      ApiResponse(
        200,
        jsonEncode({
          'meta': {
            'projection': projection,
            'schema_version': 1,
            'scope': 'personal',
            'generated_at': '2026-10-30T12:00:00Z',
          },
          'data': data,
        }),
        const {},
      );

  @override
  Future<ApiResponse> get(
    String path, {
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) async {
    if (path.contains('passport/history/$_versionId/')) {
      return _envelope('personal.me.passport.version', {
        'id': _versionId,
        'document_id': 'PM-P-20261030-11111111',
        'variant': 'complete',
        'generated_at': '2026-10-30T10:00:00Z',
        'payload': {
          'identity': {
            'name': 'Profil exemple',
            'bio': 'Présentation telle qu’émise.',
            'location': 'Lubumbashi',
            'links': const [],
            'owner_details': const {},
          },
          'interests': ['Recherche'],
          'open_to': const [],
          'activities': const [],
          'proofs': const [],
          'credentials': const [],
          'team_affiliations': const [],
          'active_space_mandates': const [],
        },
      });
    }
    if (path.contains('passport/history/')) {
      return _envelope('personal.me.passport.history', {
        'count': 1,
        'has_more': false,
        'next_offset': 1,
        'items': [
          {
            'id': _versionId,
            'document_id': 'PM-P-20261030-11111111',
            'variant': 'complete',
            'generated_at': '2026-10-30T10:00:00Z',
            'revoked': revoked,
            'active_shares': withShares && !shareRevoked && !revoked
                ? [
                    {'id': _shareId, 'expires_at': '2026-11-30T10:00:00Z'},
                  ]
                : const [],
            'integrity_ok': true,
          },
        ],
      });
    }
    return _envelope('personal.me.passport', {
      'variant': 'complete',
      'identity': {
        'name': 'Profil exemple',
        'bio': 'Présentation actuellement mise à jour.',
        'avatar_url': '',
        'links': const [],
      },
      'declared': {'interests': const [], 'open_to': const []},
      'activities': const [],
      'established': {'proofs': const []},
      'issued': {'credentials': const []},
    });
  }

  @override
  Future<ApiResponse> post(
    String path, {
    Map<String, dynamic>? body,
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) async {
    lastPostPath = path;
    postedPaths.add(path);
    if (path.contains('passport/issue/')) {
      return _envelope('personal.me.passport.issuance', {
        'id': _versionId,
        'document_id': 'PM-P-20261030-11111111',
        'variant': Uri.parse(path).queryParameters['variant'] ?? 'complete',
        'generated_at': '2026-10-30T10:00:00Z',
      });
    }
    if (path.contains('passport/history/$_versionId/share/')) {
      return _envelope('personal.me.passport.share', {
        'share_id': _shareId,
        'share_url': 'https://example.test/passport/shared/issued',
        'document_id': 'PM-P-20261030-11111111',
      });
    }
    if (path.contains('passport/history/$_versionId/revoke/')) {
      revoked = true;
      return _envelope('personal.me.passport.version', {
        'id': _versionId,
        'revoked': true,
      });
    }
    if (path.contains('passport/shares/$_shareId/revoke/')) {
      shareRevoked = true;
      return _envelope('personal.me.passport.share', {
        'share_id': _shareId,
        'revoked': true,
      });
    }
    throw StateError('Unexpected post: $path');
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _DelayedVariantApi extends _DatedPassportApi {
  final publicResult = Completer<ApiResponse>();

  @override
  Future<ApiResponse> get(
    String path, {
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) {
    if (Uri.parse(path).queryParameters['variant'] == 'public') {
      return publicResult.future;
    }
    return super.get(path, headers: headers, cancel: cancel);
  }
}

class _VariantPassportApi extends _DatedPassportApi {
  @override
  Future<ApiResponse> get(
    String path, {
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) async {
    final variant = Uri.parse(path).queryParameters['variant'];
    if (variant != null && variant != 'complete') {
      return _envelope('personal.me.passport', {
        'variant': variant,
        'identity': {
          'name': 'Profil exemple',
          'avatar_url': '',
          'links': const [],
        },
        'declared': {'interests': const [], 'open_to': const []},
        'activities': const [],
        'established': {'proofs': const []},
        'issued': {'credentials': const []},
        'topic_options': const [],
      });
    }
    return super.get(path, headers: headers, cancel: cancel);
  }
}

class _OneShotPassportApi extends _DatedPassportApi {
  int ownerFetches = 0;

  @override
  Future<ApiResponse> get(
    String path, {
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) async {
    if (path.contains('api/v1/me/passport/?variant=complete')) {
      ownerFetches++;
      return _envelope('personal.me.passport', {
        'variant': 'complete',
        'identity': {
          'name': 'Profil composé',
          'bio': 'Présentation privée',
          'links': const [],
        },
        'private_details': {
          'first_name': 'Profil',
          'last_name': 'Composé',
          'username': 'profil-compose',
          'country': 'CD',
          'phone': 'Numéro réservé',
        },
        'declared': {
          'interests': [
            {
              'id': 'public-interest',
              'topic': {'code': 'recherche', 'label': 'Recherche'},
            },
            {
              'id': 'private-interest',
              'topic': {'code': 'sante', 'label': 'Santé privée'},
            },
          ],
          'open_to': const [],
        },
        'activities': const [],
        'experiences': const [],
        'established': {'proofs': const []},
        'issued': {'credentials': const []},
        'collectives': const {},
        'topic_options': [
          {'code': 'recherche', 'label': 'Recherche'},
        ],
        'composition': {
          'schema_version': 1,
          'public_identity': {
            'name': 'Profil composé',
            'bio': 'Présentation publique',
            'links': const [],
            'presentation_details': {
              'first_name': 'Profil',
              'last_name': 'Composé',
              'username': 'profil-compose',
              'country': 'CD',
            },
          },
          'public_ids': {
            'interests': ['public-interest'],
            'open_to': const [],
            'activities': const [],
            'experiences': const [],
            'proofs': const [],
            'credentials': const [],
          },
        },
      });
    }
    return super.get(path, headers: headers, cancel: cancel);
  }
}

class _UnavailablePassportApi implements MakoloApiClient {
  @override
  Uri get baseUri => Uri.parse('https://example.test/');

  @override
  Future<ApiResponse> get(
    String path, {
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) async => throw StateError('Offline');

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  testWidgets(
    'dated Passport opens the issued content instead of live content',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(home: MePassportScreen(api: _DatedPassportApi())),
      );
      await tester.pumpAndSettle();
      expect(
        find.text('Présentation actuellement mise à jour.'),
        findsOneWidget,
      );
      await tester.tap(find.byTooltip('Versions datées'));
      await tester.pumpAndSettle();
      expect(find.text('PM-P-20261030-11111111'), findsOneWidget);
      await tester.tap(find.text('PM-P-20261030-11111111'));
      await tester.pumpAndSettle();
      expect(find.text('Présentation telle qu’émise.'), findsOneWidget);
      expect(find.text('Recherche'), findsOneWidget);
    },
  );
  testWidgets('native owner can revoke an issued version and refresh history', (
    tester,
  ) async {
    final api = _DatedPassportApi();
    await tester.pumpWidget(MaterialApp(home: MePassportScreen(api: api)));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Versions datées'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Révoquer cette version'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Révoquer la version'));
    await tester.pumpAndSettle();

    expect(api.lastPostPath, 'api/v1/me/passport/history/$_versionId/revoke/');
    expect(api.revoked, isTrue);
    expect(find.textContaining('Révoqué'), findsWidgets);
  });

  testWidgets(
    'native owner can revoke one share without revoking the version',
    (tester) async {
      final api = _DatedPassportApi(withShares: true);
      await tester.pumpWidget(MaterialApp(home: MePassportScreen(api: api)));
      await tester.pumpAndSettle();

      await tester.tap(find.byTooltip('Versions datées'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('PM-P-20261030-11111111'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Révoquer un lien de partage'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Révoquer le lien'));
      await tester.pumpAndSettle();

      expect(api.lastPostPath, 'api/v1/me/passport/shares/$_shareId/revoke/');
      expect(api.shareRevoked, isTrue);
      expect(api.revoked, isFalse);
    },
  );

  testWidgets(
    'network error is recoverable and variant controls remain available',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(home: MePassportScreen(api: _UnavailablePassportApi())),
      );
      await tester.pumpAndSettle();

      expect(find.textContaining('Passeport indisponible'), findsOneWidget);
      expect(find.text('Réessayer'), findsOneWidget);
      expect(find.text('Public'), findsOneWidget);
      await tester.tap(find.text('Réessayer'));
      await tester.pumpAndSettle();
      expect(find.text('Réessayer'), findsOneWidget);
    },
  );

  testWidgets('four Passport tabs compose locally from one owner response', (
    tester,
  ) async {
    final api = _OneShotPassportApi();
    await tester.pumpWidget(MaterialApp(home: MePassportScreen(api: api)));
    await tester.pumpAndSettle();
    expect(find.text('Présentation privée'), findsOneWidget);
    await tester.tap(find.text('Public'));
    await tester.pumpAndSettle();
    expect(find.text('Présentation publique'), findsOneWidget);
    expect(find.text('Présentation privée'), findsNothing);
    expect(find.text('Numéro réservé'), findsNothing);
    expect(find.text('Informations personnelles'), findsOneWidget);
    expect(find.text('Profil'), findsOneWidget);
    expect(find.text('Composé'), findsOneWidget);
    expect(find.text('CD'), findsOneWidget);
    expect(find.text('Recherche'), findsWidgets);
    expect(find.text('Santé privée'), findsNothing);
    await tester.tap(find.text('Thématique'));
    await tester.pumpAndSettle();
    expect(find.text('Présentation publique'), findsOneWidget);
    expect(find.text('Informations personnelles'), findsOneWidget);
    await tester.tap(find.text('Personnalisé'));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
      find.text('Informations personnelles'),
      250,
      scrollable: find
          .descendant(
            of: find.byType(ListView).first,
            matching: find.byType(Scrollable),
          )
          .first,
    );
    expect(find.text('Informations personnelles'), findsOneWidget);
    expect(api.ownerFetches, 1);
  });

  testWidgets('switching Passport variant never paints previous private data', (
    tester,
  ) async {
    final api = _DelayedVariantApi();
    await tester.pumpWidget(MaterialApp(home: MePassportScreen(api: api)));
    await tester.pumpAndSettle();
    expect(find.text('Présentation actuellement mise à jour.'), findsOneWidget);

    await tester.tap(find.text('Public'));
    await tester.pump();
    expect(find.text('Présentation actuellement mise à jour.'), findsNothing);

    api.publicResult.complete(
      api._envelope('personal.me.passport', {
        'variant': 'public',
        'identity': {'name': 'Profil public', 'links': const []},
        'declared': {'interests': const [], 'open_to': const []},
        'activities': const [],
        'established': {'proofs': const []},
        'issued': {'credentials': const []},
      }),
    );
    await tester.pumpAndSettle();
    expect(find.text('Profil public'), findsOneWidget);
    expect(find.text('Présentation actuellement mise à jour.'), findsNothing);
  });

  testWidgets('version issuance remains available when sharing a selection', (
    tester,
  ) async {
    final api = _VariantPassportApi();
    await tester.pumpWidget(MaterialApp(home: MePassportScreen(api: api)));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Public'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Partager le Passeport'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Copier le lien du Passeport'));
    await tester.pumpAndSettle();
    expect(
      api.postedPaths.any(
        (p) =>
            p.contains('api/v1/me/passport/issue/') &&
            p.contains('variant=public'),
      ),
      isTrue,
    );
    expect(
      api.postedPaths.any(
        (p) => p.contains('api/v1/me/passport/history/$_versionId/share/'),
      ),
      isTrue,
    );
  });

  testWidgets(
    'main share sheet keeps exactly four actions, history is separate',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(home: MePassportScreen(api: _VariantPassportApi())),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Partager le Passeport'));
      await tester.pumpAndSettle();
      expect(find.text('Partager le PDF'), findsOneWidget);
      expect(find.text('Partager dans Makolo'), findsOneWidget);
      expect(find.text('Partager le lien public'), findsOneWidget);
      expect(find.text('Copier le lien du Passeport'), findsOneWidget);
      expect(find.text('Partager une ancienne version'), findsNothing);
      await tester.pageBack();
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Versions datées'));
      await tester.pumpAndSettle();
      expect(find.byTooltip('Partager cette version'), findsOneWidget);
      expect(find.byTooltip('Télécharger cette version'), findsOneWidget);
      expect(find.byTooltip('Révoquer cette version'), findsOneWidget);
    },
  );

  testWidgets(
    'public and empty thematic variants retain the identity baseline',
    (tester) async {
      final api = _VariantPassportApi();
      await tester.pumpWidget(MaterialApp(home: MePassportScreen(api: api)));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Public'));
      await tester.pumpAndSettle();
      expect(find.text('Profil exemple'), findsOneWidget);
      expect(
        find.textContaining('uniquement les informations renseignées'),
        findsNothing,
      );

      await tester.tap(find.text('Thématique'));
      await tester.pumpAndSettle();
      expect(find.text('Profil exemple'), findsOneWidget);
      expect(find.textContaining('Aucun thème sélectionnable'), findsNothing);
    },
  );
}
