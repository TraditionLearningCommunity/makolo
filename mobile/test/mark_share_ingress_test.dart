import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/platform/sharing/system_share_receiver.dart';
import 'package:makolo_mobile/runtime/runtime_ingress.dart';

void main() {
  test('a share bound to one Profile cannot be consumed by another', () async {
    final ingress = RuntimeIngress();
    addTearDown(ingress.close);
    ingress.offerShare(
      const SharedPayload(kind: SharedPayloadKind.text, text: 'Private A'),
      profileId: 'profile-a',
    );
    expect(ingress.takeShare(profileId: 'profile-b'), isNull);
    expect(ingress.hasPendingShare, isFalse);
  });

  test('an unauthenticated Android share can be claimed after login', () async {
    final ingress = RuntimeIngress();
    addTearDown(ingress.close);
    ingress.offerShare(
      SharedPayload(
        kind: SharedPayloadKind.url,
        url: Uri.parse('https://example.org/activity'),
      ),
    );
    final payload = ingress.takeShare(profileId: 'signed-in-profile');
    expect(payload?.kind, SharedPayloadKind.url);
    expect(payload?.url.toString(), 'https://example.org/activity');
    expect(ingress.hasPendingShare, isFalse);
  });

  test(
    'temporary share queue stays bounded and leaves no background owner',
    () async {
      final ingress = RuntimeIngress();
      addTearDown(ingress.close);
      for (var i = 0; i < 8; i++) {
        ingress.offerShare(
          SharedPayload(kind: SharedPayloadKind.text, text: 'shared-$i'),
          profileId: 'profile-a',
        );
      }
      final entries = <String>[];
      while (ingress.hasPendingShare) {
        final next = ingress.takeShare(profileId: 'profile-a');
        if (next?.text != null) entries.add(next!.text!);
      }
      expect(entries, [
        'shared-3',
        'shared-4',
        'shared-5',
        'shared-6',
        'shared-7',
      ]);
      ingress.discardShares();
      expect(ingress.hasPendingShare, isFalse);
    },
  );
}
