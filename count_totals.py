#! /usr/bin/env python

"""statis.py  -- Stampa le statistiche delle colonne di un file indicate come parametro 
                 nella riga di comando

Usage 1: statis.py [-k pos.len[,pos.len...]]  [-s] [-c] [-H] [-f pos.len[,pos.len ...]] [file]
Usage 2: statis.py [-k col[,col...]] -dchar   [-s] [-c] [-H] [-f col[,col...]]          [file]
Usage 3: statis.py -T -k pos.len -f pos.len   [file]

Opzioni:
  -k pos.len          la posizione della chiave secondo la quale vengono calcolati i totali
  -f pos.len          la posizione del campo (o dei campi) da sommare:
                      se vengono richiesti piu' di un campo da sommare, viene visualizzato
                      sulla destra anche il loro totale, prima dell'ultimo  campo records.
      --csv           file di input in formato csv
  -d, --delim=DELIM   separatore di campi del file. Sottindende True il parametro --csv
                      Le opzioni -f e -k devono essere nel formato: -k|-f col[,col...]
  -P, --pivot=N       crea una tabella pivot
                      N deve essere un numero e deve corrispondere alla Nma chiave di ragruppamento:
                      N=1 corrisponde alla  -kpos1.len1      (prima chiave)
                      N=2 corrisponde alla  -k...,pos2.len2 (seconda chiave)
                      Le regole da seguire sono:
                      a) Il numero delle chiavi -k deve essere tra 1 e 2 
                        (ovvero ci deve essere almeno una chiave e non piu' di 2).
                      b) Se le chiavi sono 2 (-kpos1.len1,pos2.len2), (e conseguentemente 1<=N<=2),
                         allora, deve esserci al massimo una sola colonna da sommare (-f pos1.len1).
  -R, --range         visualizza due colonne con i valori MIN e MAX della chiave di raggruppamento.
                      Da usare insieme con l'opzione -P|--pivot.
      --output_csv    produce l'output in formato .csv (come separatore di default il carattere ';')
                      default 'False'.
      --output_delim  definisce il separatore di output in formato .csv
                      (imposta 'True' il parametro --output_csv).
  -s                  il separatore delle migliaia
  -H, --noheader      non viene visualizzato l'header nell'output (incompatibile con --pivot)
  -C, --nocents       visualizza i valori per intero (default divisione per 100)
  -T, --totals        visualizza l'ultima colonna (o le ultime due colonne) dei totali
  -h, --help          stampa questo messaggio
"""

"""
key          sum1         recs

AL              21           2
AR               2           1

total           23           3


key            AL           AR    total

sum1            21           2       23

recs             2           1        3

------------------------------
key           sum1          sum2         total        recs

AL              21            60            81           2
AR               2            30            32           1

total           23            90           113           3


key             AL            AR         total

sum1            21             2            23
sum2            60            30            90

total           81            32           113
recs             2             1             3
------------------------------

"""

__author__ = ["Ardian Vesho (ardian.vesho.uni@tesoro.it)",]
__version__ = "$1, 0, 0 $"
__date__ = "$Date: 2007/12/10 $"

import sys, getopt
from collections import defaultdict
from copy import deepcopy


### impostazioni di default
delim = ""           # campi a larghezza fissa
opt_header=1         # header
opt_totals=1         # totali
opt_pivot=""         # non-pivot table
opt_range=""         # 
opt_cents=1          # divisione per 100
opt_input_csv=""     # non_csv
opt_output_csv=""    # non_csv
opt_output_delim=""  # non_csv
param_keys, param_sums = "", ""

# tabella di conversione da valori negativi Cobol a numerici
# cobol
chars = 'pqrstuvwxy'
cobol2num = dict([(c, str(chars.index(c))) for c in chars])    # {'p':'0', 'q':'1', 'r':'2', 's':'3', 't':'4', 'u':'5', 'v':'6', 'w':'7', 'x':'8', 'y':'9'}
# mainframe
chars = '}JKLMNOPQR'
cobol2num.update([(c, str(chars.index(c))) for c in chars])    # {'K': '2', 'J': '1', 'M': '4', 'L': '3', 'O': '6', 'N': '5', 'Q': '8', 'P': '7', 'R': '9', '}': '0'}
# convenzione MEF
chars = 'AJKLMNOPQR'
cobol2num.update([(c, str(chars.index(c))) for c in chars])    # {'A': '0', 'K': '2', 'J': '1', 'M': '4', 'L': '3', 'O': '6', 'N': '5', 'Q': '8', 'P': '7', 'R': '9'}
# oppure: 
#cobol2num = dict([(chars[i], str(i)) for i in range(len(chars))])
                                            

def usage(code, msg=''):
    if msg:
        sys.stderr.write(msg+"\n")
    else:
        sys.stderr.write(__doc__ % globals()+"\n")
    sys.exit(code)

def process_arg(arg="", delim=delim):
    """
    if delim == "": -[kf] pos.len[,pos.len...]
    else:           -[kf] col[,col...]
    """
    if not arg: return []
    ret = []
    for elem in arg.split(","):
        if delim:
            ret.append(int(elem)-1)
        else:
            pos, length = map(int, elem.split("."))
            ret.append([pos-1, pos+length-1])    # pos1, pos2: 0-based index
    return ret

def check_numeric_values(number):
    """gestisce i valori numerici negativi formato Cobol"""
    try:
        return int(number)                   # se la stringa di input e' numerico, finisce qui
    except:
        if not number: return 0
        lastchar=cobol2num[number[-1]]         # converte l'ultimo carattere in numerico
        number='-' + number[:-1] + lastchar    # aggiunge il segno '-' all'inizio
        return int(number)

    
#####################################
# http://code.activestate.com/recipes/498181-add-thousands-separator-commas-to-formatted-number/
# Code from Michael Robellard's comment made 28 Feb 2010
# Modified for leading +, -, space on 1 Mar 2010 by Glenn Linderman
# 
# Tail recursion removed and  leading garbage handled on March 12 2010, Alessandro Forghieri
#
# Second version:
# >>> locale.setlocale(locale.LC_ALL, "")
# 'English_United States.1252'
# >>> locale.format('%d', 12345, True)
# '12,345'
#
def splitThousands( s, tSep=',', dSep='.'):
    '''Splits a general float on thousands. GIGO on general input'''
    if s == None:
        return 0
    if not isinstance( s, str ):
        s = str( s )

    cnt=0
    numChars=dSep+'0123456789'
    ls=len(s)
    while cnt < ls and s[cnt] not in numChars: cnt += 1

    lhs = s[ 0:cnt ]
    s = s[ cnt: ]
    if dSep == '':
        cnt = -1
    else:
        cnt = s.rfind( dSep )
    if cnt > 0:
        rhs = dSep + s[ cnt+1: ]
        s = s[ :cnt ]
    else:
        rhs = ''

    splt=''
    while s != '':
        splt= s[ -3: ] + tSep + splt
        s = s[ :-3 ]

    return lhs + splt[ :-1 ] + rhs


def rotatematrix(data):
    newdata=[]
    for i in range(len(data[0])):
        newrow=[data[j][i] for j in range(len(data))]
        newdata.append(newrow)
    return newdata


def massage_data_with_range(totals):
    if not totals: return

    # nel caso di opt_range, si prospettano solo i valori min e max, e tot_rec
    totals_new = defaultdict(lambda: [None,None,0])

    # inizialmente, si contano le colonne nuove (opt_pivot contiene la chiave iniziale che viene trasformata in col)
    ind_xaxis = opt_pivot - 1   # base-0
    xaxis = sorted(set(key[ind_xaxis] for key in totals.keys()))

    for (key, value) in totals.items():
        l = list(key)
        new_val = l.pop(ind_xaxis)
        new_key = tuple(l)
        if (totals_new[new_key][0] is None) or (new_val < totals_new[new_key][0]):
            totals_new[new_key][0] = new_val
        if (totals_new[new_key][1] is None) or (new_val > totals_new[new_key][1]):
            totals_new[new_key][1] = new_val
        totals_new[new_key][2] += value[-1]    # value = [sum1, sum2...sumn, tot_rec]  -> tot_rec

    #  Adesso il dictionary viene trasformato in una matrice (una lista di liste), in cui 
    #+ la prima riga contiene le diciture dei campi, e la prima colonna le chiavi del dictionary
    list_totals = []

    header = ['key', 'min', 'max']
    if opt_totals:
        header +=['recs']
    list_totals.append(header)
    tot_gen = [0]*(len(header)-1)

    for (key, value) in sorted(totals_new.iteritems()):
        new_key   = ' '.join(key)
        new_value = value[:2]                   # da [min, max, rec] -> [min, max]
        list_totals.append([new_key]+value)     # inserisce in testa 'key'

    # alla fine restituisce list_totals
    return list_totals


def massage_data_no_range(totals):
    if not totals: return

    # viene raggruppato nuovamente il dictionary secondo la chiave di pivot, 
    if opt_pivot:
        
        # inizialmente, si contano le colonne nuove (opt_pivot contiene la chiave iniziale che viene trasformata in col)
        ind_xaxis = opt_pivot - 1   # base-0
        xaxis = sorted(set(key[ind_xaxis] for key in totals.keys()))

        # nel caso di una nuova chiave, il valore di default e' [None, None...,0]
        totals_new = defaultdict(lambda: [None]*(len(xaxis))+[0])
    
        for (key, value) in totals.items():
            l = list(key)
            new_col = l.pop(ind_xaxis)
            new_key = tuple(l)
            ind_col = xaxis.index(new_col)
            if totals_new[new_key][ind_col] is None:
                totals_new[new_key][ind_col]  = value[0]   # in modalita' pivot puo' esserci solo un campo da sommare, cioe' len(value)=1.
            else:
                totals_new[new_key][ind_col] += value[0]
            # aggiorna anche l'ultimo campo, 'recs'
            totals_new[new_key][-1] += value[-1]

    else:
        totals_new = deepcopy(totals)


    #  Adesso il dictionary viene trasformato in una matrice (una lista di liste), in cui 
    #+ la prima riga contiene le diciture dei campi, e la prima colonna le chiavi del dictionary
    list_totals = []

    # first_value contiene almeno il valore tot_rec ([...,tot_rec])
    first_value = totals_new.values()[0]
    header = ['key']
    if opt_pivot:
        header += xaxis
    else:
        header +=['sum%d'%(i+1) for i in range(len(first_value)-1)]  # considera solo i campi sum
    
    if opt_totals:
        if (param_sums) and len(first_value) > 2:   # i campi 'sums' senza l'ultimo campo 'recs'
            header +=['total']        # se i campi 'sums' sono piu' di uno, si aggiunge il campo 'total', prima dell'ultimo campo 'recs'
        header +=['recs']
    list_totals.append(header)

    # in 'list_totals' vengono aggiunti i dati, con l'accortezza di impostare il penultimo
    # campo 'total', con la somma dei campi precedenti; in piu' viene aggiunto alla 
    # fine la riga dei totali generali
    tot_gen = [0]*(len(header)-1)

    for (key, value) in sorted(totals_new.iteritems()):
        tot_value=0
        new_value=[]

        # prima elabora i campi sum: [sum1...sumn, tot_rec] -> [sum1...sumn]
        i=0
        for v in value[:-1]:
            if v != None:
                if opt_cents: v /= 100.0
                tot_value  +=v
                tot_gen[i] +=v
            i+=1
            new_value.append(v)

        # aggiunge il tot_sums (se ci sono almeno 2 campi sum)
        if opt_totals and param_sums and len(value)>2:
            new_value.append(tot_value)
            tot_gen[-2] +=tot_value
        # infine tot_rec
        new_value.append(value[-1])
        tot_gen[-1] +=value[-1]

        new_key = ' '.join(key)
        list_totals.append([new_key]+new_value)     # inserisce in testa 'key'

    # alla fine restituisce list_totals
    list_totals.append(['total']+tot_gen)           # alla fine inserisce la riga dei totali generali
    return list_totals


def print_totals_with_range(totals):
    if not totals: return

    # all'inizio manipola i dati, raggruppando per la chiave
    list_totals = massage_data_with_range(totals)
    if not list_totals: return

    # se viene richiesta l'output in formato csv, non ci si preoccupa della formattazione:
    if opt_output_csv:
        if opt_header:
            print opt_output_delim.join(list_totals[0])
        num_row = 1
        for row in list_totals[1:]:
            num_row+=1
            print opt_output_delim.join([str(v) for v in row])
        return
    
    # calcola la larghezza massima della prima colonna (key), e delle altre colonne (sums)
    len_first_col = max([len(row[0]) for row in list_totals])       # verifica il primo campo di tutte le rige, overo 'key'          (['AL', 21.0, 60.0, 81.0, 2]  -> 'AL')
    len_other_cols= max([len(str(n)) for n in list_totals[1]])      # verifica tutti i campi della SECONDA riga, ovvero della testata  (['key', 'AL', 'AR', 'total'] -> 'key')
    if len_first_col <5: len_first_col=5

    # header
    if opt_header:
        row=list_totals[0] 
        s = []
        fmt="%%-%ss"%len_first_col
        s.append(fmt % row[0])
        for value in row[1:]:
            fmt=" %%%ss"%len_other_cols
            s.append(fmt % value)
        print ''.join(s)

    # ciclo sui dati
    num_row = 1
    for row in list_totals[1:]:
        num_row+=1
        s = []
        fmt="%%-%ss"%len_first_col
        s.append(fmt % row[0])
        for value in row[1:]:
            fmt=" %%%ss"%len_other_cols
            s.append(fmt % value)
        print ''.join(s)
    # if opt_range, i totali generali mancano


def print_totals_no_range(totals):
    if not totals: return

    # all'inizio manipola i dati, raggruppando per la chiave
    list_totals = massage_data_no_range(totals)
    if not list_totals: return

    # se viene richiesta l'output in formato csv, non ci si preoccupa della formattazione:
    if opt_output_csv:
        if opt_header:
            print opt_output_delim.join(list_totals[0])
        num_row = 1
        for row in list_totals[1:]:
            num_row+=1
            if num_row == len(list_totals): print  # aggiunge una riga vuota prima dei totali generali
            print opt_output_delim.join([str(v) for v in row])
        return
    
    # calcola la larghezza massima della prima colonna (key), e delle altre colonne (sums)
    len_first_col = max([len(row[0]) for row in list_totals])       # verifica il primo campo di tutte le rige, overo 'key'          (['AL', 21.0, 60.0, 81.0, 2]  -> 'AL')
    len_other_cols= max([len(str(n)) for n in list_totals[0]])      # verifica tutti i campi della PRIMA   riga, ovvero della testata  (['key', 'AL', 'AR', 'total'] -> 'key')
    if len_first_col <5: len_first_col=5
    if (param_sums) and len_other_cols <13:
        len_other_cols=13

    # header
    if opt_header:
        row=list_totals[0] 
        s = []
        fmt="%%-%ss"%len_first_col
        s.append(fmt % row[0])
        for value in row[1:]:
            fmt=" %%%ss"%len_other_cols
            s.append(fmt % value)
        print ''.join(s)

    # le righe di dettaglio
    num_row = 1
    for row in list_totals[1:]:
        num_row+=1
        s = []
        fmt="%%-%ss"%len_first_col
        s.append(fmt % row[0])
        # tutti i sums, eccetto l'ultimo campo: tot_rec
        for value in row[1:-1]:
            if value != None:
                if opt_cents:
                    fmt=" %%%s.2f"%len_other_cols
                else:
                    fmt=" %%%s.0f"%len_other_cols
            else:
                fmt=" %%%ss"%len_other_cols
            s.append(fmt % value)
            # tot_rec
        if opt_totals:
            fmt=" %%%ss"%len_other_cols
            s.append(fmt % row[-1])

        # aggiunge una riga vuota prima dei totali generali
        if num_row == len(list_totals): print
        print ''.join(s)


def runfile(fileinp):

    # crea un dictionary con valore di default [0,0...max_sums,tot_rec]
    num_values = len(param_sums) + 1
    totals = defaultdict(lambda: [0]*num_values)

    if opt_input_csv:
        import csv
        reader = csv.reader(fileinp, delimiter=delim)
        for row in reader:
            # keys e' una tuple di valori
            keys=tuple([row[i] for i in param_keys])
            values=[check_numeric_values(row[i]) for i in param_sums]
            i=0
            for i, val in values:          # caricamento dei totali 
                totals[keys][i]+=val
                i+=1
            # tot_rec
            totals[keys][-1]+=1
    else:
        for line in fileinp:
            # keys e' una tuple di valori
            keys=tuple([line[p1:p2] for (p1,p2) in param_keys])
            values=[check_numeric_values(line[p1:p2]) for (p1,p2) in param_sums]
            i=0
            for val in values:          # caricamento dei totali 
                totals[keys][i]+=val
                i+=1
            # tot_rec
            totals[keys][-1]+=1

    if not totals: return
    if opt_range:
        print_totals_with_range(totals)
    else:
        print_totals_no_range(totals)


def check_arguments():
    global param_keys, param_sums, delim, opt_pivot, opt_input_csv, opt_output_csv, opt_output_delim, opt_cents

    # se viene passato il parametro --opt_output_delim, significa che l'output deve essere in formato .csv
    if opt_input_csv:
        if not delim: delim=";"
    elif delim:
        opt_input_csv=1

    # se viene passato il parametro --opt_output_delim, significa che l'output deve essere in formato .csv
    if opt_output_delim:
        opt_output_csv=1
    elif opt_output_csv:
        opt_output_delim=";"

    try:
        param_keys=process_arg(param_keys, delim)
        param_sums=process_arg(param_sums, delim)
    except:
        usage(1, "ERR: parametri non corretti.\n%s %s" % (sys.exc_info()[0], sys.exc_info()[1]))
        usage(1, "%s %s" % (sys.exc_info()[0], sys.exc_info()[1]))

    # range
    if opt_range and (not opt_pivot):
        usage(1, "usage: -R: manca il parametro -P (pivot) .")

    # se non si sono campi da sommare, opt_cents non ha senso
    if opt_range or (not param_sums):
        opt_cents=""

    # la richiesta di pivot-table e' piu restrittiva
    if opt_pivot:
        if not opt_pivot.isdigit():
            usage(1, "usage: -P deve essere un numero.")
        opt_pivot = int(opt_pivot)
        if len(param_keys) == 0:
            usage(1, "usage: -P: ci deve essere almeno una chiave di raggruppamento -k.")
#        elif len(param_keys) > 2:
#            usage(1, "usage: -P: ci possono essere al massimo 2 chiavi di raggruppamento -k.")
        elif (opt_pivot < 1) or (opt_pivot > len(param_keys)):
            usage(1, "usage: -P: il valore deve essere una delle chiavi di raggruppamento -k.")
        elif (len(param_sums) > 1):
            usage(1, "usage: -P: in modalita' pivot non possono esserci piu' di una colonna da sommare.")
        if not opt_header:
            usage(1, "usage: -P e -H incompatibili.")
     
    
def main():
    global delim, opt_header, opt_cents, opt_totals, opt_pivot, opt_range, opt_input_csv, opt_output_csv, opt_output_delim
    global param_keys, param_sums
    
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hsHCTRP:d:k:f:",
                                   ["help", "totals", "csv", "delim=", "pivot=", "range", \
                                   "nocents", "no-cents", "no_cents", \
                                   "noheader", "no-header", "no_header", \
                                   "output_csv", "output-csv", "output_delim=", "output-delim="])
    except getopt.error, err:
        usage(1, err.msg)
    for opt, optarg in opts:
        if opt in ('-h', '--help'):
            usage(0)
        elif opt in ('-k'):
            param_keys = optarg
        elif opt in ('-f'):
            param_sums = optarg
        elif opt in ('-d', '--delim',):
            delim = optarg
        elif opt in ('-P', '--pivot',):
            opt_pivot = optarg
        elif opt in ('-T', '--totals'):
            opt_totals = 1
        elif opt in ('-R', '--range'):
            opt_range = 1
        elif opt in ('-C', '--nocents', '--no-cents', '--no_cents'):
            opt_cents = ""
        elif opt in ('-H', '--noheader', '--no-header', '--no_header',):
            opt_header = 0
        elif opt in ('--csv',):
            opt_input_csv = 1
        elif opt in ('--output_csv', '--output-csv',):
            opt_output_csv = 1
        elif opt in ('--output_delim', '--output-delim',):
            opt_output_delim = optarg

    check_arguments()
    file=(len(args) >= 1 and open(args[0])) or sys.stdin
    #runfile(file)
    runfile(file)


if __name__ == '__main__':
    main()
