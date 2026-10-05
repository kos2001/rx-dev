export const environments={
  pusht:{name:'PushT',dataset:'lerobot/pusht',input:'물체·로봇 위치와 각도'},
  aloha:{name:'ALOHA · Peg insertion',dataset:'lerobot/aloha_sim_insertion_scripted',input:'MuJoCo 관절·물체 자세와 속도'},
  libero_drawer:{name:'LIBERO · 가운데 서랍 열기',dataset:'lerobot/libero',input:'두 카메라 영상 + 8차원 로봇 상태',methods:['act','diffusion']},
  libero_basket:{name:'LIBERO · 수프 통조림 바구니 넣기',dataset:'lerobot/libero',input:'두 카메라 영상 + 8차원 로봇 상태',methods:['act','diffusion']},
  transfer:{name:'ALOHA · Cube transfer',dataset:'lerobot/aloha_sim_transfer_cube_scripted',input:'MuJoCo 관절·물체 자세와 속도'}
};
export const environmentOf=config=>config.environment || Object.keys(environments).find(key=>environments[key].dataset===config.dataset) || 'pusht';
export const canEvaluate=config=>!config.dataset || config.dataset===environments[environmentOf(config)].dataset;
