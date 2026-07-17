import i18n from 'i18next'
import{initReactI18next}from'react-i18next'

const common={
 title:'iRacing Analyst',sessions:'Sessions',import:'Import telemetry',waiting:'Waiting for iRacing',recording:'Recording',
 best:'Best lap',median:'Median pace',optimal:'Sector optimal',potential:'Potential gap',corners:'Corners and zones',
 noSession:'Import an IBT/NPZ file or complete an iRacing session.',selected:'Best',reference:'Median',sourceLap:'Source lap',
 loss:'Available gain',speed:'Speed',throttle:'Throttle',brake:'Brake',steering:'Steering',delta:'Delta',map:'Track and racing line',
 whyFaster:'Why this lap was faster',improve:'What to improve next run',noInsights:'No reliable difference was found yet.',
 delete:'Delete',clear:'Clear test data',confirmClear:'Delete every locally recorded session?',validLaps:'valid laps',turns:'turns',
 trajectoryMissing:'The racing line was not recorded in this older session.',confirmed:'Confirmed',probable:'Probable',insufficient:'Not enough data',zone:'Zone',
 'data.ready':'Enough laps for reliable comparisons.','data.limited':'Initial comparison; repeat the session to confirm the pattern.',
 'data.needMoreLaps':'Complete at least 3 valid laps to compare best and median.','data.noValidLaps':'No complete valid laps were recorded.','data.insufficient':'This legacy report does not contain enough structured data.',
 'insight.faster.title':'Best lap gained time here','insight.faster.message':'This section was measurably faster than your median lap.',
 'rec.inconsistent.title':'Build consistency','rec.inconsistent.message':'Repeat the reference inputs before pushing the entry. This segment has the largest spread.',
 'rec.lateThrottle.title':'Reach full throttle earlier','rec.lateThrottle.message':'The throttle ramp is long after the apex. Prioritize rotation before acceleration.',
 'rec.lowSpeed.title':'Protect minimum speed','rec.lowSpeed.message':'Avoid over-slowing the car; use the source lap as the entry reference.',
 'rec.corrections.title':'Reduce steering corrections','rec.corrections.message':'Unwind the steering progressively and delay throttle if the car is not settled.',
 'rec.segment.title':'Focus on this segment','rec.segment.message':'Reproduce the source lap inputs; this is the largest confirmed time opportunity.'
}
const ru={
 ...common,title:'iRacing Аналитик',sessions:'Сессии',import:'Импорт телеметрии',waiting:'Ожидание iRacing',recording:'Идёт запись',
 best:'Лучший круг',median:'Медианный темп',optimal:'Sector Optimal',potential:'Потенциал',corners:'Повороты и зоны',
 noSession:'Импортируйте IBT/NPZ или завершите сессию iRacing.',selected:'Лучший',reference:'Медианный',sourceLap:'Круг-источник',
 loss:'Доступный выигрыш',speed:'Скорость',throttle:'Газ',brake:'Тормоз',steering:'Руль',delta:'Дельта',map:'Карта и траектория',
 whyFaster:'Почему этот круг быстрее',improve:'Что улучшить в следующем заезде',noInsights:'Надёжной разницы пока не найдено.',
 delete:'Удалить',clear:'Удалить тестовые данные',confirmClear:'Удалить все локально записанные сессии?',validLaps:'валидных кругов',turns:'поворотов',
 trajectoryMissing:'В этой старой сессии траектория не записывалась.',confirmed:'Подтверждено',probable:'Вероятно',insufficient:'Мало данных',zone:'Зона',
 'data.ready':'Кругов достаточно для надёжного сравнения.','data.limited':'Первичный вывод: повторите сессию, чтобы подтвердить закономерность.',
 'data.needMoreLaps':'Проедьте минимум 3 валидных круга для сравнения лучшего и медианного.','data.noValidLaps':'Не записано ни одного полного валидного круга.','data.insufficient':'В старом отчёте недостаточно структурированных данных.',
 'insight.faster.title':'Здесь лучший круг выиграл время','insight.faster.message':'Этот участок пройден измеримо быстрее медианного круга.',
 'rec.inconsistent.title':'Закрепи повторяемость','rec.inconsistent.message':'Сначала повтори действия референса, не переатаковывая вход: здесь самый большой разброс.',
 'rec.lateThrottle.title':'Раньше выходи на полный газ','rec.lateThrottle.message':'После апекса газ набирается долго. Сосредоточься на повороте машины до разгона.',
 'rec.lowSpeed.title':'Сохрани минимальную скорость','rec.lowSpeed.message':'Не замедляй машину лишний раз; используй круг-источник как ориентир входа.',
 'rec.corrections.title':'Уменьши коррекции рулём','rec.corrections.message':'Плавно распускай руль и не добавляй газ, пока машина не стабилизирована.',
 'rec.segment.title':'Сосредоточься на сегменте','rec.segment.message':'Повтори действия круга-источника: здесь подтверждена крупнейшая потеря времени.'
}
i18n.use(initReactI18next).init({resources:{en:{translation:common},ru:{translation:ru}},lng:localStorage.getItem('language')||'ru',fallbackLng:'en',interpolation:{escapeValue:false}})
export default i18n
