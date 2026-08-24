class engine:
    def numwords(self, num, wantlist=False,
                 group=0, comma=',', andword='and',
                 zero='zero', one='one', decimal='point',
                 threshold=None):
        '''
        Return a number in words.

        group = 1, 2 or 3 to group numbers before turning into words
        comma: define comma
        andword: word for 'and'. Can be set to ''.
            e.g. "one hundred and one" vs "one hundred one"
        zero: word for '0'
        one: word for '1'
        decimal: word for decimal point
        threshold: numbers above threshold not turned into words
        
        parameters not remembered from last call. Departure from Perl version.
        '''
        self.number_args = dict(andword=andword, zero=zero, one=one)
        num = '%s' % num
    
        # Handle "stylistic" conversions (up to a given threshold)...
        if (threshold is not None and
             float(num) > threshold):
            spnum = num.split('.',1)
            while (comma):
                    (spnum[0], n) = subn(r"(\d)(\d{3}(?:,|\Z))",r"\1,\2", spnum[0])
                    if n==0:
                        break
            try:
                return "%s.%s" % (spnum[0], spnum[1])
            except IndexError:
                return "%s" % spnum[0]
            
        if group < 0 or group > 3:
            raise BadChunkingOptionError 
        nowhite = num.lstrip()
        if nowhite[0] == '+':
            sign = "plus"
        elif nowhite[0] == '-':
            sign = "minus"
        else:
            sign = ""
    
        myord =  (num[-2:] in ('st', 'nd', 'rd', 'th'))
        if myord:
            num = num[:-2]
        if decimal:
            if group != 0:
                chunks = num.split('.')
            else:
                chunks = num.split('.',1)
        else:
            chunks = [num]


        first = 1
        loopstart = 0

        if chunks[0] == '':
            first = 0
            if len(chunks) > 1:
                loopstart = 1

        for i in range(loopstart, len(chunks)):
            chunk = chunks[i]
            #remove all non numeric \D
            chunk = resub(r"\D", self.blankfn, chunk)
            if chunk == "":
                chunk = "0"

            if group != 0 and first != 0:
                chunk = self.enword(chunk, 1)
            else:
                chunk = self.enword(chunk, group)

            if chunk[-2:] == ', ':
                chunk = chunk[:-2]
            chunk = resub(r"\s+,", self.commafn, chunk)
            if group != 0 and first:
                chunk = resub(r", (\S+)\s+\Z", "%s \1" % andword, chunk)
            chunk = resub(r"\s+", self.spacefn, chunk)
            #chunk = resub(r"(\A\s|\s\Z)", self.blankfn, chunk)
            chunk = chunk.strip()
            if first:
                first = ''
            chunks[i] = chunk

        numchunks = []
        if first != 0:
            numchunks = chunks[0].split("%s " % comma)

        if myord and numchunks:
            #TODO: can this be just one re as it is in perl?
            mo = search(r"(%s)\Z" % ordinal_suff, numchunks[-1])
            if mo:
                numchunks[-1] = resub(r"(%s)\Z" % ordinal_suff , ordinal[mo.group(1)],
                                      numchunks[-1])
            else:
                numchunks[-1] += 'th'

        for chunk in chunks[1:]:
            numchunks.append(decimal)
            numchunks.extend(chunk.split("%s " % comma))

        #wantlist: Perl list context. can explictly specify in Python
        if wantlist:
            if sign:
                numchunks = [sign] + numchunks
            return numchunks
        elif group:
            signout = "%s " % sign if sign else ''
            return "%s%s" % (signout, ", ".join(numchunks))
        else:
            signout = "%s " % sign if sign else ''
            num = "%s%s" % (signout, numchunks.pop(0))
            first = not num.endswith(decimal)
            for nc in numchunks:
                if nc == decimal:
                    num += " %s" % nc
                    first = 0
                elif first:
                    num += "%s %s" % (comma, nc)
                else:
                    num += " %s" % nc
            return num
