import {forwardRef} from 'react';

import {type SVGIconProps, SvgIcon} from './svgIcon';

const IconRewind10 = forwardRef<SVGSVGElement, SVGIconProps>((props, ref) => {
  return (
    <SvgIcon {...props} ref={ref}>
      <path d="M2.18,2.64c-.05-.07-.07-.14-.06-.22,.01-.08,.05-.15,.12-.2L4.62,.34c.06-.04,.12-.09,.18-.13,.06-.04,.13-.06,.2-.06h.86c.08,0,.15,.03,.21,.09,.06,.06,.09,.13,.09,.21V7.56c0,.08-.03,.15-.09,.21s-.13,.09-.21,.09h-.89c-.08,0-.15-.03-.21-.09s-.09-.13-.09-.21V2.12l-1.56,1.22c-.07,.05-.14,.07-.21,.06-.08-.01-.15-.05-.2-.12l-.52-.65Z" />
      <path d="M13.47,3.03c0,.14,.01,.29,.01,.46v1.03c0,.17,0,.32-.01,.46-.02,.43-.09,.82-.19,1.18-.11,.36-.27,.68-.51,.95s-.53,.48-.9,.63c-.37,.15-.82,.23-1.36,.23s-1-.08-1.36-.23c-.37-.15-.67-.36-.9-.63s-.4-.58-.51-.95-.17-.76-.19-1.18c-.01-.28-.02-.6-.02-.95s0-.67,.02-.95c.02-.42,.09-.82,.19-1.19,.11-.37,.28-.69,.51-.96s.53-.49,.9-.64c.37-.16,.82-.24,1.36-.24s.99,.08,1.36,.22c.37,.15,.67,.36,.9,.63,.23,.27,.4,.58,.51,.95,.11,.36,.17,.76,.19,1.18Zm-4.43,1.9c.04,.53,.16,.94,.38,1.23,.22,.29,.58,.43,1.09,.43s.88-.15,1.09-.43c.22-.29,.34-.7,.38-1.23,.01-.28,.02-.59,.02-.92s0-.65-.02-.92c-.04-.53-.16-.94-.38-1.23-.22-.29-.58-.43-1.09-.43s-.88,.14-1.09,.43c-.22,.29-.34,.7-.38,1.23-.01,.28-.02,.59-.02,.92s0,.64,.02,.92Z" />
      <path d="M3.65,15.99c-.19,0-.38-.07-.53-.22L.25,12.9c-.29-.29-.29-.77,0-1.06l2.88-2.88c.29-.29,.77-.29,1.06,0s.29,.77,0,1.06l-2.35,2.35,2.35,2.35c.29,.29,.29,.77,0,1.06-.15,.15-.34,.22-.53,.22Z" />
      <path d="M13.2,13.12H.78c-.41,0-.75-.34-.75-.75s.34-.75,.75-.75H13.2c.69,0,1.25-.56,1.25-1.25v-2.61c0-.41,.34-.75,.75-.75s.75,.34,.75,.75v2.61c0,1.52-1.23,2.75-2.75,2.75Z" />
    </SvgIcon>
  );
});

IconRewind10.displayName = 'IconRewind10';

export {IconRewind10};
