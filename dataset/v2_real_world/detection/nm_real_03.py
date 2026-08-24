class FacebookIE:
    def _real_extract(self, url):
        mobj = re.match(self._VALID_URL, url)
        video_id = mobj.group('id')

        url = 'https://www.facebook.com/video/video.php?v=%s' % video_id
        webpage = self._download_webpage(url, video_id)

        BEFORE = '{swf.addParam(param[0], param[1]);});\n'
        AFTER = '.forEach(function(variable) {swf.addVariable(variable[0], variable[1]);});'
        m = re.search(re.escape(BEFORE) + '(.*?)' + re.escape(AFTER), webpage)
        if not m:
            m_msg = re.search(r'class="[^"]*uiInterstitialContent[^"]*"><div>(.*?)</div>', webpage)
            if m_msg is not None:
                raise ExtractorError(
                    'The video is not available, Facebook said: "%s"' % m_msg.group(1),
                    expected=True)
            else:
                raise ExtractorError('Cannot parse data')
        data = dict(json.loads(m.group(1)))
        params_raw = compat_urllib_parse.unquote(data['params'])
        params = json.loads(params_raw)
        video_data = params['video_data'][0]
        video_url = video_data.get('hd_src')
        if not video_url:
            video_url = video_data['sd_src']
        if not video_url:
            raise ExtractorError('Cannot find video URL')

        video_title = self._html_search_regex(
            r'<h2 class="uiHeaderTitle">([^<]*)</h2>', webpage, 'title',
            fatal=False)
        if not video_title:
            video_title = self._html_search_regex(
                r'(?s)<span class="fbPhotosPhotoCaption".*?id="fbPhotoPageCaption"><span class="hasCaption">(.*?)</span>',
                webpage, 'alternative title', default=None)
            if len(video_title) > 80 + 3:
                video_title = video_title[:80] + '...'
        if not video_title:
            video_title = 'Facebook video #%s' % video_id

        return {
            'id': video_id,
            'title': video_title,
            'url': video_url,
            'duration': int(video_data['video_duration']),
            'thumbnail': video_data['thumbnail_src'],
        }
