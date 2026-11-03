import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

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
