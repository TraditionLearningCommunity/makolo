import 'package:connectivity_plus/connectivity_plus.dart';

class DeviceConnectivity {
  const DeviceConnectivity();

  Future<bool> isOffline() async {
    try {
      final results = await Connectivity().checkConnectivity();
      return results.isNotEmpty &&
          results.every((result) => result == ConnectivityResult.none);
    } on Object {
      return false;
    }
  }
}
