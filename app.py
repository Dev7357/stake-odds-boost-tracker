import os, requests, streamlit as st
st.set_page_config(page_title='Stake Boost Monitor', page_icon='🟡', layout='wide')
st.title('🟡 Stake Soccer Boost Monitor')
st.caption('Phone-friendly dashboard for authorized Stake Sports Data API data')
API_BASE='https://odds-data.stake.com'
API_KEY=os.getenv('STAKE_API_KEY','')
if not API_KEY:
    st.error('STAKE_API_KEY is not configured. Add it as a server secret/environment variable.')
    st.stop()
HEADERS={'Authorization':f'Bearer {API_KEY}'}
def get(path):
    r=requests.get(API_BASE+path,headers=HEADERS,timeout=20); r.raise_for_status(); return r.json()
def find_boost_fields(v,path='root'):
    out=[]
    if isinstance(v,dict):
        m={k:x for k,x in v.items() if any(w in str(k).lower() for w in ('boost','promotion','promoted'))}
        if m: out.append({'path':path,'fields':m})
        for k,x in v.items(): out += find_boost_fields(x,f'{path}.{k}')
    elif isinstance(v,list):
        for i,x in enumerate(v): out += find_boost_fields(x,f'{path}[{i}]')
    return out
try:
    sports=get('/sports')
except Exception as e:
    st.error(f'API connection failed: {e}'); st.stop()
if not any(s.get('slug') in ('soccer','football') for s in sports):
    st.warning('Soccer was not found in the returned API data.')
st.success('Stake Sports Data API connected.')
st.subheader('Automatic confirmed-boost scan')
st.warning('This app labels a selection as CONFIRMED only when the source explicitly exposes boost/promotion metadata. Ordinary odds movement is not treated as an official boost.')
hits=find_boost_fields(sports)
if hits: st.success('Explicit boost/promotion data found.'); st.json(hits[:50])
else: st.info('No explicit boost/promotion field was exposed by the returned public API data.')
st.subheader('Check a fixture')
fixture_id=st.text_input('Fixture ID')
if st.button('Check fixture odds') and fixture_id:
    try:
        data=get(f'/odds/{fixture_id}'); hits=find_boost_fields(data)
        if hits: st.success('Explicit boost/promotion information found.'); st.json(hits)
        else:
            st.info('No explicit boost/promotion field found for this fixture.');
            with st.expander('Raw API response'): st.json(data)
    except Exception as e: st.error(str(e))
st.divider(); st.caption('Never enter a Stake password, session cookie, or private login token.')
