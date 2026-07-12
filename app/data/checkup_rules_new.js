/**
 * CMC Health Screening Platform
 * app/data/checkup_rules_new.js — 종합검진 선택검사 Rule (Rule Engine 데이터)
 *
 * ★ Single Source of Truth: 2025.12.24 리플렛 (25.12.24 리플렛_천안의료원 종합건강검진센터4.pdf)
 * ★ 리플렛에 없는 규칙은 넣지 않는다. 항목 문구는 리플렛 표기를 그대로 따른다.
 * ★ UI는 이 Rule을 읽어 렌더링만 한다 — UI에 Rule을 하드코딩하지 않는다.
 *
 * 구조:
 *   Program → Selection Group(id/name/count) → Allowed Item(id) → Restriction/Note
 *   - group.count      : 해당 그룹에서 선택해야 하는 항목 수 (초과 선택 불가, 부족 시 진행 불가)
 *   - item.note        : 리플렛에 명시된 부가 문구 (그대로 표기)
 *   - item.restriction : 리플렛에 명시된 제한 (gender: '여성' 등) — 명시된 것만 기록
 *   - item.recommended / recommendReason : AI 추천 Badge·사유 표시용 (추천 로직은 이후 구현)
 *   - program.pricing  : 가격 표시 Rule (display=true면 UI에 프로그램 가격 표시)
 *   - Rule이 없는 프로그램(YOUNG, 온김에검진 등)은 선택검사 그룹을 표시하지 않는다.
 *
 * 새 프로그램 추가 시: 이 파일에 programs['새ID']만 추가하면 UI가 자동 반영된다.
 */
'use strict';

const CMC_CHECKUP_RULES = {
  version: '2025.12.24',
  source: '25.12.24 리플렛_천안의료원 종합건강검진센터4',

  /* 공통 안내 (리플렛 ※ 문구) */
  commonNotes: [
    '조직검사 및 대장용종절제술 시행 시 비용 추가',
    '위내시경 수면비 별도(5만) 비용 발생 (공단위암검진 동시 시행 시 비용청구 없음)',
  ],

  /* ─── 검사 항목 사전 (리플렛 표기 그대로) ─── */
  items: {
    /* 초음파 */
    US_ABD:      { label: '복부초음파' },
    US_CAROTID:  { label: '경동맥초음파' },
    US_BREAST:   { label: '유방초음파', note: '유방촬영 필수' },
    US_THYROID:  { label: '갑상선초음파' },
    US_PROSTATE: { label: '전립선초음파' },
    US_GYN:      { label: '부인과초음파' },
    /* CT촬영검사 */
    CT_VFAT:     { label: '내장비만CT' },
    CT_CACS:     { label: '심장Ca(칼슘)CT', note: '관상동맥석회화 위험도' },
    CT_BRAIN:    { label: '뇌CT' },
    CT_CSPINE:   { label: '경추CT' },
    CT_LSPINE:   { label: '요추CT' },
    CT_LDCT:     { label: '저선량 흉부(폐)CT' },
    /* 내시경·혈액 */
    COLON_NOSED: { label: '대장내시경(비수면)', note: '조직검사 또는 시술시 추가 비용 발생' },
    ALZ:         { label: '알츠온검사', note: '혈액검사, 알츠하이머 위험도 평가검사' },
    CARDIO_BNP:  { label: '심혈관인자검사', note: '혈액검사, pro BNP' },
    /* MRI/MRA (VIP·PREMIUM B그룹) */
    MRI_BRAIN:   { label: 'MRI 뇌(두부)' },
    MRI_LSPINE:  { label: 'MRI 요추' },
    MRI_CSPINE:  { label: 'MRI 경추' },
    MRI_PROSTATE:{ label: 'MRI 전립선' },
    MRI_SHOULDER:{ label: 'MRI 어깨' },
    MRI_KNEE:    { label: 'MRI 무릎', note: '우측, 좌측 각각 개별' },
    MRA_BRAIN_NECK:  { label: 'MRA촬영 : 뇌(두부)/목(경부)' },
    MRA_HEAD_NECK:   { label: 'MRA촬영 : 두경부(BRAIN+NECK)' },
    MRIMRA_SCREEN:   { label: 'MRI+MRA(Screen cut) : 뇌(두부, Brain)' },
    HEART_US:    { label: '심장초음파', note: '오후검진' },
    /* 혈액·기타 (B/C그룹) */
    TM_CYFRA:    { label: '폐암표지자(CYFRA 21-1)' },
    TM_CA724:    { label: '난소 및 소화기암표지자(CA 72-4)' },
    TM_CA153:    { label: '유방암표지자(CA15-3)' },
    VASC1:       { label: '혈관질환위험성검사1(Homosystein)' },
    VASC2:       { label: '혈관질환위험성검사2(D-DIMER)' },
    IMM1:        { label: '면역질환검사1(류마티스, Anti-CCP)' },
    IMM2:        { label: '면역질환검사2(자가면역질환, ANA)' },
    ANEMIA:      { label: '빈혈정밀검사(Fe,TIBC,UIBC,Ferritin)' },
    BMD2:        { label: '골밀도2부위', note: '기본1부위에서 2부위로 변경' },
    CDCOPY:      { label: 'CD Copy(당일 영상자료)' },
    ARTERIO:     { label: '동맥경화도 검사', note: '말초혈관검사, 대사질환합병증' },
    HPV:         { label: '인유두종바이러스 검사', note: '여성, 부인과검사', restriction: { gender: '여성' } },
    SED_COLON:   { label: '수면비 감면(대장내시경)', note: '대장내시경 수면 선택시' },
    SED_GASTRO:  { label: '수면비 감면(위내시경)',   note: '위내시경 수면 선택시' },
  },

  /* ─── 프로그램별 Rule ─── */
  programs: {

    BASIC: {
      pricing: { display: true, male: '440,000원', female: '490,000원' },
      groups: [
        { id: 'A', name: 'A그룹', count: 2,
          items: ['US_ABD','US_CAROTID','US_BREAST','US_THYROID','US_GYN',
                  'CT_VFAT','CT_CACS','CT_BRAIN','CT_CSPINE','CT_LSPINE','CT_LDCT',
                  'COLON_NOSED'] },
        { id: 'B', name: 'B그룹', count: 2,
          items: ['TM_CYFRA','TM_CA724','TM_CA153','VASC1','VASC2','IMM1','IMM2',
                  'ANEMIA','BMD2','CDCOPY','ARTERIO','HPV','SED_COLON','SED_GASTRO'] },
      ],
    },

    SMART: {
      pricing: { display: true, male: '770,000원', female: '820,000원' },
      groups: [
        { id: 'A', name: 'A그룹', count: 5,
          items: ['US_ABD','US_CAROTID','US_BREAST','US_THYROID','US_GYN',
                  'CT_VFAT','CT_CACS','CT_BRAIN','CT_CSPINE','CT_LSPINE','CT_LDCT',
                  'COLON_NOSED','ALZ'] },
        { id: 'B', name: 'B그룹', count: 2,
          items: ['TM_CYFRA','TM_CA724','TM_CA153','VASC1','VASC2','IMM1','IMM2',
                  'ANEMIA','BMD2','CDCOPY','ARTERIO','HPV','SED_COLON','SED_GASTRO'] },
      ],
    },

    VIP: {
      pricing: { display: true, male: '1,100,000원', female: '1,200,000원' },
      groups: [
        { id: 'A', name: 'A그룹', count: 5,
          items: ['US_ABD','US_CAROTID','US_BREAST','US_THYROID','US_PROSTATE','US_GYN',
                  'CT_VFAT','CT_CACS','CT_BRAIN','CT_CSPINE','CT_LSPINE','CT_LDCT',
                  'COLON_NOSED','ALZ','CARDIO_BNP'] },
        { id: 'B', name: 'B그룹', count: 1,
          items: ['MRI_BRAIN','MRI_LSPINE','MRI_CSPINE','MRI_PROSTATE','MRI_SHOULDER','MRI_KNEE',
                  'MRA_BRAIN_NECK','HEART_US'] },
        { id: 'C', name: 'C그룹', count: 3,
          items: ['TM_CYFRA','TM_CA724','TM_CA153','VASC1','VASC2','IMM1','IMM2',
                  'ANEMIA','CDCOPY','ARTERIO','HPV','SED_COLON','SED_GASTRO'] },
      ],
    },

    PREMIUM: {
      pricing: { display: true, male: '1,300,000원', female: '1,400,000원' },
      groups: [
        { id: 'A', name: 'A그룹', count: 5,
          items: ['US_ABD','US_CAROTID','US_BREAST','US_THYROID','US_PROSTATE','US_GYN',
                  'CT_VFAT','CT_CACS','CT_BRAIN','CT_CSPINE','CT_LSPINE','CT_LDCT',
                  'COLON_NOSED','ALZ','CARDIO_BNP'] },
        { id: 'B', name: 'B그룹', count: 2,
          items: ['MRI_BRAIN','MRI_LSPINE','MRI_CSPINE','MRI_PROSTATE','MRI_SHOULDER','MRI_KNEE',
                  'MRA_HEAD_NECK','MRIMRA_SCREEN','HEART_US'] },
        { id: 'C', name: 'C그룹', count: 3,
          items: ['TM_CYFRA','TM_CA724','TM_CA153','VASC1','VASC2','IMM1','IMM2',
                  'ANEMIA','CDCOPY','ARTERIO','HPV','SED_COLON','SED_GASTRO'] },
      ],
    },
  },

  /* ─── Rule 조회 헬퍼 (Rule Engine API) ─── */
  getProgram(programId) { return this.programs[programId] || null; },
  hasSelection(programId) { return !!this.programs[programId]; },
  getItem(itemId) { return this.items[itemId] || null; },
};
