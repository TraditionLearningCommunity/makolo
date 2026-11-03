import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/navigation/profile_portrait_store.dart';

void main() {
  test('profile photo accepts only authenticated same-origin media paths', () {
    final base = Uri.parse('https://makolo.example/');
    expect(
      ProfilePortraitStore.authorizedPath('/private_media/avatar.jpg', base),
      '/private_media/avatar.jpg',
    );
    expect(
      ProfilePortraitStore.authorizedPath(
        'https://makolo.example/private_media/avatar.png',
        base,
      ),
      '/private_media/avatar.png',
    );
    expect(
      ProfilePortraitStore.authorizedPath(
        'https://makolo.example:444/private_media/avatar.png',
        base,
      ),
      isNull,
    );
    expect(
      ProfilePortraitStore.authorizedPath(
        'https://other.example/private_media/avatar.png',
        base,
      ),
      isNull,
    );
    expect(
      ProfilePortraitStore.authorizedPath('//other.example/avatar.png', base),
      isNull,
    );
    expect(
      ProfilePortraitStore.authorizedPath('javascript:alert(1)', base),
      isNull,
    );
  });
}
