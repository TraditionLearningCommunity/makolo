import 'package:flutter/widgets.dart';
import 'package:flutter_svg/flutter_svg.dart';

class MakoloMark extends StatelessWidget {
  const MakoloMark({super.key, this.size = 36, this.white = false});

  final double size;
  final bool white;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'Makolo',
      image: true,
      child: SvgPicture.asset(
        white
            ? 'assets/brand/makolo-mark-white.svg'
            : 'assets/brand/makolo-mark-violet.svg',
        width: size,
        height: size,
        fit: BoxFit.contain,
      ),
    );
  }
}
