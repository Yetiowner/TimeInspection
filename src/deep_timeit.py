import inspect as inspector
import time
import copy
import tkinter
import colorsys
import matplotlib

CHUNK_ADJACENCIES = {"if ": ["elif ", "else:"], "try:": ["except ", "except:", "finally:"]}

class Time():
    def __init__(self, start, end, time, indentation, nextindentation=None):
        self.start = start
        self.end = end
        self.time = time
        self.indentation = len(indentation)
        self.nextindentation = len(nextindentation) if nextindentation else nextindentation
    
    def __repr__(self):
        return str([self.start, self.end, self.time, self.indentation, self.nextindentation])

class Info():
    def __init__(self, lines, times, removed):
        self.lines = lines
        self.times = times
        self.removed = removed
    
    def show(self, mintimetotrigger=None):
        MAXX = 100
        MAXY = 30
        root = tkinter.Tk()
        root.title(" Function display ")

        scroll_v = tkinter.Scrollbar(root)
        scroll_v.pack(side = tkinter.RIGHT, fill = "y")
        scroll_h = tkinter.Scrollbar(root, orient = tkinter.HORIZONTAL)
        scroll_h.pack(side = tkinter.BOTTOM, fill = "x")

        Output = tkinter.Text(root, width = min(MAXX, max([len(i) for i in self.lines])), height = min(MAXY, len(self.lines)), yscrollcommand = scroll_v.set, xscrollcommand = scroll_h.set, wrap = tkinter.NONE)

        scroll_h.config(command = Output.xview)
        scroll_v.config(command = Output.yview)

        for index, line in enumerate(self.lines):
            Output.insert(tkinter.INSERT, line+("\n" if index != len(self.lines)-1 else ""))
        mintime = 0
        maxtime = max(self.times, key=lambda x: x.time).time
        for index, timeset in enumerate(self.times):
            rgb = colorsys.hsv_to_rgb(((1-timeset.time/maxtime) if maxtime > (mintimetotrigger if mintimetotrigger else 0) else 1) / 3., 1.0, 1.0)
            col = [round(255*x) for x in rgb]
            Output.tag_config(index, background=rgb_to_hex(col))
            setCol(Output, timeset, index, self.lines)
        Output.tag_config("failed", background="#00FFFF")
        for index, timeset in enumerate(self.removed):
            setCol(Output, timeset, "failed", self.lines)
        Output.config(state=tkinter.DISABLED)
        Output.pack()
        tkinter.mainloop()

def setCol(Output, timeset, index, lines):
    Output.tag_add(index, f'{timeset.start+1}.0+{timeset.indentation}c', f'{timeset.start+1}.0+{len(lines[timeset.start])}c')
    for endpos in range(timeset.start+1, timeset.end+1):
        Output.tag_add(index, f'{endpos+1}.0+{timeset.indentation}c', f'{endpos+1}.0+{timeset.nextindentation}c')

def rgb_to_hex(rgb):
    return matplotlib.colors.to_hex([i/255 for i in rgb])

def deepTimeit(func, args=[], kwargs={}, reattempt=True, show=True, mintime=None):
    alltimesvar = "dicttimes"
    allcountsvar = "dictcounts"
    allintervaledvar = "dictintervalled"
    linetimevar = "linetime"
    maxrepeats = 100000
    lines = inspector.getsource(func).rstrip().split("\n")
    newlines = []
    for line in lines:
        validline = True
        if line.lstrip() == "":
            validline = False
        if line.lstrip().startswith("#"):
            validline = False
        if validline:
            newlines.append(line)
    lines = newlines
    caller_frame = inspector.stack()[1]
    caller_module = inspector.getmodule(caller_frame[0])
    start = lines[0]
    oldstart = copy.deepcopy(start)
    lines = lines[1:]
    oldlines = copy.deepcopy(lines)
    needsToRedo = True
    ignores = []
    removedChunks = []

    while needsToRedo:
        lines = copy.deepcopy(oldlines)
        start = copy.deepcopy(oldstart)
        timedChunksIndices = getChunksToTime(lines)
        newchunks = []
        for index, chunk in enumerate(timedChunksIndices):
            if index not in ignores:
                newchunks.append(chunk)
            else:
                removedChunks.append(chunk)
        timedChunksIndices = newchunks
        newlines = []
        newlines.append(start)
        openbrace = "{"
        closebrace = "}"
        firstlineindentation = getIndentation(lines[1])
        for var in [alltimesvar, allcountsvar, allintervaledvar]:
            newlines.append(firstlineindentation+f"{var} = {openbrace}{closebrace}")
            newlines.append(firstlineindentation+f"for i in range({len(timedChunksIndices)}):")
            if var != allintervaledvar:
                newlines.append(firstlineindentation+f"  {var}[i] = 0")
            else:
                newlines.append(firstlineindentation+f"  {var}[i] = False")

        for lineindex, line in enumerate(lines):
            starttimerstoadd = []
            for timerindex, i in enumerate(timedChunksIndices):
                if lineindex == i[0]:
                    starttimerstoadd.append(timerindex)
            for start in starttimerstoadd:
                newlines.append(getIndentation(line)+f"if {allcountsvar}[{start}] < {maxrepeats}:")
                newlines.append(getIndentation(line)+f"    {linetimevar}{start} = time.time()")
            newlines.append(line)
            endtimerstoadd = []
            for timerindex, i in enumerate(timedChunksIndices):
                if lineindex == i[1]:
                    endtimerstoadd.append([timerindex, getIndentation(lines[i[0]])])
            endtimerstoadd.sort(reverse=True, key=lambda x: x[0])
            for end, ind in endtimerstoadd:
                newlines.append(ind+f"if {allcountsvar}[{end}] < {maxrepeats}:")
                newlines.append(ind+f"    {alltimesvar}[{end}] += time.time()-{linetimevar}{end}")
                newlines.append(ind+f"    {allcountsvar}[{end}] += 1")
        
        for newlineindex, newline in enumerate(newlines):
            if newline.lstrip().startswith("return"):
                if newline.lstrip().startswith("return "):
                    newlines[newlineindex] += f", {alltimesvar}, {allcountsvar}"
                else:
                    newlines[newlineindex] += f" {alltimesvar}, {allcountsvar}"
            else:
                newlines.append(f"{getIndentation(lines[1])}return {alltimesvar}, {allcountsvar}")

        
        lines = "\n".join(newlines)
        strtoexec = "\n"+lines
        #print(strtoexec)
        localcopy = locals()
        globalcopy = globals()
        try:
            globalcopy.update(caller_module.__dict__)
        except AttributeError:
            pass
        try:
            exec(strtoexec, globalcopy, localcopy)
        except SyntaxError:
            print(strtoexec)
            raise SyntaxError
        funcname = func.__name__
        exec(f"totaltime = time.time()\nreturnval = {funcname}(*args, **kwargs)\ntotaltime = time.time()-totaltime", globals(), localcopy)
        results = localcopy["returnval"]
        totaltime = localcopy["totaltime"]
        try:
            counts = results[-1]
            times = results[-2]
        except TypeError:
            print(strtoexec)
            raise TypeError
        maxx = max(counts.values())
        if maxx == maxrepeats and reattempt:
            needsToRedo = True
            ignores = []
            for i in counts:
                if counts[i] == maxrepeats:
                    ignores.append(i)
        else:
            needsToRedo = False
    alltimes = []
    alltimes.append(Time(0, len(oldlines), totaltime, "", getIndentation(oldlines[0])))
    for timex in times:
        alltimes.append(Time(timedChunksIndices[timex][0]+1, timedChunksIndices[timex][1]+1, times[timex], getIndentation(oldlines[timedChunksIndices[timex][0]]), None if timedChunksIndices[timex][0]+1 == timedChunksIndices[timex][1]+1 else getIndentation(oldlines[timedChunksIndices[timex][0]+1])))
    
    removedTimes = []
    for chunk in removedChunks:
        removedTimes.append(Time(chunk[0]+1, chunk[1]+1, None, getIndentation(oldlines[chunk[0]]), None if chunk[0]+1 == chunk[1]+1 else getIndentation(oldlines[chunk[0]+1])))
    
    infoobj = Info([oldstart]+oldlines, alltimes, removedTimes)
    if show:
        infoobj.show(mintime)
    else:
        return infoobj



def getChunksToTime(lines):
    indices = []
    for index, line in enumerate(lines):
        if line.lstrip().startswith("return "):
            continue
        lineindentation = getIndentation(line)
        nextlineindentation = getIndentation(lines[min(index+1, len(lines)-1)])
        if nextlineindentation <= lineindentation:
            indices.append([index, index])
        else:
            adjacentchunktitles = []
            for i in CHUNK_ADJACENCIES:
                for j in CHUNK_ADJACENCIES[i]:
                    adjacentchunktitles.append(j)
            shouldcont = False
            for i in adjacentchunktitles:
                if lines[index].lstrip().startswith(i):
                    shouldcont = True
            if shouldcont:
                continue
            nextIndexWhereLEQ = len(lines)-1
            for newindex in range(index+1, len(lines)):
                if getIndentation(lines[newindex]) <= lineindentation:
                    partofadjacent = False
                    for key in CHUNK_ADJACENCIES:
                        if lines[index].lstrip().startswith(key):
                            partofadjacent = CHUNK_ADJACENCIES[key]
                    if partofadjacent != False:
                        oneofadjacent = False
                        for potadj in partofadjacent:
                            if lines[newindex][len(getIndentation(lines[index])):].startswith(potadj):
                                oneofadjacent = True
                        if not(oneofadjacent):
                            nextIndexWhereLEQ = newindex-1
                            break    
                    else:
                        nextIndexWhereLEQ = newindex-1
                        break
            indices.append([index, nextIndexWhereLEQ])
    
    return indices

def shouldAddTimer(lines, lineindex):
    if lineindex != len(lines)-1 and getIndentation(lines[lineindex]) < getIndentation(lines[lineindex+1]):
        return False
    if lines[lineindex].lstrip().startswith("return "):
        lines[lineindex] = ""
        return False
    return True


def getIndentation(line):
    try:
        return " "*line.index(line.lstrip()[0])
    except:
        return ""

def factorial(a, b, extraadd = True):
    import random
    t = 1
    time.sleep(0.05)
    time.sleep(1/20)
    try:
        x = 1
    except:
        y = 1
    #asdf
    for i in range(1, a*b):

        t *= i
        x = 0
        y = 0
        if extraadd:
            for i in range(100000):

                y += i

                if i < 500:
                    x += i
                    x += random.randint(1, 100)
    return t

deepTimeit(deepTimeit, args=[factorial], kwargs={"args":[5, 5]})
#deepTimeit(factorial, args=[5, 5])