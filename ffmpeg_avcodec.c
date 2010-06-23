/* test avcodec.h for legacy location */

#include <ffmpeg/avcodec.h>

int main(void)
    {
    static const int v = LIBAVCODEC_VERSION_INT;
    return 0;
    }

