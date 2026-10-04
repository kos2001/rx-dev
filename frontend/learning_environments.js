export const environments={
  pusht:{name:'PushT',dataset:'lerobot/pusht',input:'물체·로봇 위치와 각도'},
  aloha:{name:'ALOHA · Peg insertion',dataset:'lerobot/aloha_sim_insertion_scripted',input:'MuJoCo 관절·물체 자세와 속도'},
  transfer:{name:'ALOHA · Cube transfer',dataset:'lerobot/aloha_sim_transfer_cube_scripted',input:'MuJoCo 관절·물체 자세와 속도'}
};
export const environmentOf=config=>config.environment || Object.keys(environments).find(key=>environments[key].dataset===config.dataset) || 'pusht';
export const canEvaluate=config=>!config.dataset || config.dataset===environments[environmentOf(config)].dataset;
