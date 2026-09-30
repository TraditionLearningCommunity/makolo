import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/platform/permissions/permission_gateway.dart';

class FakePermissionGateway implements PermissionGateway {
  FakePermissionGateway({
    required this.current,
    this.requested = PermissionDecision.granted,
  });

  PermissionDecision current;
  PermissionDecision requested;
  int requestCount = 0;

  @override
  Future<bool> openSettings() async => true;

  @override
  Future<PermissionDecision> request(MakoloPermission permission) async {
    requestCount += 1;
    return requested;
  }

  @override
  Future<PermissionDecision> status(MakoloPermission permission) async =>
      current;
}

void main() {
  test('granted permission is not requested again', () async {
    final gateway = FakePermissionGateway(current: PermissionDecision.granted);

    expect(
      await gateway.requestWhenNeeded(MakoloPermission.camera),
      PermissionDecision.granted,
    );
    expect(gateway.requestCount, 0);
  });

  test(
    'denied permission is requested only on explicit capability action',
    () async {
      final gateway = FakePermissionGateway(
        current: PermissionDecision.denied,
        requested: PermissionDecision.permanentlyDenied,
      );

      expect(
        await gateway.requestWhenNeeded(MakoloPermission.camera),
        PermissionDecision.permanentlyDenied,
      );
      expect(gateway.requestCount, 1);
    },
  );

  test('settings-required permission is not re-prompted', () async {
    final gateway = FakePermissionGateway(
      current: PermissionDecision.permanentlyDenied,
    );

    expect(
      await gateway.requestWhenNeeded(MakoloPermission.locationWhenInUse),
      PermissionDecision.permanentlyDenied,
    );
    expect(gateway.requestCount, 0);
  });
}
