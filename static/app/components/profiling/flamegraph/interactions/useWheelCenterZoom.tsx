import {useCallback} from 'react';

import {type CanvasPoolManager} from 'sentry/utils/profiling/canvasScheduler';
import {type CanvasView} from 'sentry/utils/profiling/canvasView';
import {type FlamegraphCanvas} from 'sentry/utils/profiling/flamegraphCanvas';
import {getCenterScaleMatrix} from 'sentry/utils/profiling/gl/utils';

export function useWheelCenterZoom(
  canvas: FlamegraphCanvas | null,
  view: CanvasView<any> | null,
  canvasPoolManager: CanvasPoolManager
) {
  const zoom = useCallback(
    (evt: WheelEvent) => {
      if (!canvas || !view) {
        return;
      }

      const scale = 1 - evt.deltaY * 0.01 * -1; // -1 to invert scale
      canvasPoolManager.dispatch('transform config view', [
        getCenterScaleMatrix(scale, evt.offsetX, evt.offsetY, view, canvas),
        view,
      ]);
    },
    [canvas, view, canvasPoolManager]
  );

  return zoom;
}
