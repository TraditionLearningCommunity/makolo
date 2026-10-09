import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/now/now_media_viewer.dart';
import 'package:makolo_mobile/presentation/contracts/now_presentation.dart';

NowMediaBindingPresentation binding({
  bool authorized = true,
  String? url = '/api/v1/me/now/media/journey-artifacts/11111111-2222-4333-8444-555555555555/',
}) => NowMediaBindingPresentation(
  resourceRef: 'journey_artifact:11111111-2222-4333-8444-555555555555',
  target: NowMediaTarget.situation,
  purpose: NowMediaPurpose.prepare,
  kind: NowMediaKind.pdf,
  authorized: authorized,
  url: url,
);

void main() {
  test('only owner-authorized first-party API media can be opened', () {
    expect(
      nowAuthorizedMediaPath(binding()),
      'api/v1/me/now/media/journey-artifacts/11111111-2222-4333-8444-555555555555/',
    );
    expect(nowAuthorizedMediaPath(binding(authorized: false)), isNull);
    expect(nowAuthorizedMediaPath(binding(url: null)), isNull);
    expect(nowAuthorizedMediaPath(binding(url: 'https://evil.test/x')), isNull);
    expect(nowAuthorizedMediaPath(binding(url: '//evil.test/x')), isNull);
    expect(nowAuthorizedMediaPath(binding(url: '/media/private/file')), isNull);
    expect(
      nowAuthorizedMediaPath(binding(url: '/api/v1/../../secrets')),
      isNull,
    );
    expect(nowAuthorizedMediaPath(binding(url: '/api/v1/x//file')), isNull);
  });

  test(
    'temporary file suffix is selected by explicitly declared media kind',
    () {
      expect(nowMediaExtension(binding()), 'pdf');
      expect(
        nowMediaExtension(
          NowMediaBindingPresentation(
            resourceRef: 'photo:1',
            target: NowMediaTarget.situation,
            purpose: NowMediaPurpose.understand,
            kind: NowMediaKind.image,
            mimeType: 'image/png',
            authorized: true,
          ),
        ),
        'png',
      );
      expect(
        nowMediaExtension(
          NowMediaBindingPresentation(
            resourceRef: 'video:1',
            target: NowMediaTarget.situation,
            purpose: NowMediaPurpose.understand,
            kind: NowMediaKind.video,
            mimeType: 'video/mp4',
            authorized: true,
          ),
        ),
        'mp4',
      );
    },
  );
}
