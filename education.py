"""Module Compares Educ. Life Expectancy of Many Countries"""
# -*- coding: utf-8 -*-
import bs4
import requests
import csv
import sqlite3 as lite
import os
import re
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import statsmodels.formula.api as smf

URL = ('http://web.archive.org/web/20110514112442/http://unstats.un.org/unsd/'
       'demographic/products/socind/education.htm')

COUNTRIES_RENAMED = {
    "Vietnam": "Viet Nam",
    "Yemen, Rep.": "Yemen",
    "Bolivia": "Bolivia (Plurinational State of)",
    "Cabo Verde": "Cape Verde",
    "Congo, Rep.": "Congo",
    "Congo, Dem. Rep.": "Democratic Republic of the Congo",
    "Cote d'Ivoire": u"Côte d'Ivoire",
    "Egypt, Arab Rep.": "Egypt",
    "Gambia, The": "Gambia",
    "Iran, Islamic Rep.": "Iran (Islamic Republic of)",
    "Kyrgyz Republic": "Kyrgyzstan",
    "Lao PDR": "Lao People's Democratic Republic",
    "Libya": "Libyan Arab Jamahiriya",
    "Korea, Rep.": "Republic of Korea",
    "Moldova": "Republic of Moldova",
    "St. Lucia": "Saint Lucia",
    "St. Vincent and the Grenadines": "Saint Vincent and the Grenadines",
    "Slovak Republic": "Slovakia",
    "Macedonia, FYR": "TFYR of Macedonia",
    "United Kingdom": "United Kingdom of Great Britain and Northern Ireland",
    "Tanzania": "United Republic of Tanzania",
    "United States": "United States of America",
    "Venezuela, RB": "Venezuela (Bolivarian Republic of)",
    "Macao SAR, China": "China, Macao SAR",
    "Hong Kong SAR, China": "China, Hong Kong SAR",
}


def create_db():
    """Make database for educational life span"""
    conn = lite.connect('world_ed.db')
    curs = conn.cursor()
    curs.execute('DROP TABLE if exists ed_life;')
    curs.execute('CREATE TABLE ed_life (id INTEGER PRIMARY KEY AUTOINCREMENT, '
                 'country TEXT, year TEXT, total INTEGER, men INTEGER, '
                 'women INTEGER, gdp NUMERIC)')
    conn.commit()
    conn.close()


def scrape_data():
    """Scrape web page for educational life span of many countries"""
    req = requests.get(URL)
    soup = bs4.BeautifulSoup(req.content)
    rows = soup.findAll('tr')[18:201]
    regex = re.compile('^[a-h]?$')
    result = []
    for row in rows:
        data = tuple([td.text.strip() for td in row.findAll('td')
                      if not regex.match(td.text.strip())])
        if len(data) != 5:
            print "Found a weird one!"
            print data
        else:
            result.append(data)
    return result


def populate_db(scraped_data):
    """Fill database with values"""
    conn = lite.connect('world_ed.db')
    curs = conn.cursor()
    ins_sql = ('INSERT INTO ed_life (country, year, total, men, women) '
               'VALUES (? , ?, ?, ?, ?)')
    with conn:
        for tup in scraped_data:
            curs.execute(ins_sql, tup)


def add_gdp(csvfile='ny.gdp.mktp.cd_Indicator_en_csv_v2.csv'):
    """Add gdp data to database"""
    if not os.path.isfile(csvfile):
        error_msg = ('Missing csv file. The script cannot continue until '
                     'you download the GDP data. Go to: "http://api.world'
                     'bank.org/v2/en/indicator/ny.gdp.mktp.cd?download'
                     'format=csv" and put the csv file in this scripts '
                     'working directory')
        raise Exception(error_msg)

    conn = lite.connect('world_ed.db')
    curs = conn.cursor()
    with open(csvfile, 'rU') as in_file:
        next(in_file)
        next(in_file)
        fieldnames = [s.replace('"', '') for s in next(in_file).split(',')]
        d_reader = csv.DictReader(in_file, fieldnames=fieldnames)
        for line in d_reader:
            country = line['Country Name']
            if country in COUNTRIES_RENAMED:
                country = COUNTRIES_RENAMED[country]
            with conn:
                curs.execute('select * from ed_life where '
                             'country = "' + country + '"')
                try:
                    year = curs.fetchone()[2]
                except TypeError:
                    # No education data for that row, so no need to keep GDP
                    continue
                gdp = line[year]
                if gdp == '':
                    print "No GDP data that year for {}".format(country)
                    continue
                curs.execute('update ed_life set gdp = "' + gdp +
                             '" where country = "' + country + '"')


def profile_data():
    """Provide basic summary stats of education data"""
    conn = lite.connect('world_ed.db')
    dframe = pd.read_sql_query('select country, men, women from ed_life', conn)
    fig, (ax1, ax2) = plt.subplots(2, sharey=True)
    fig.subplots_adjust(hspace=0.6)
    ax1.hist(dframe['men'])
    ax1.set_title('Men: School Life Expectancy')
    ax1.set_xlabel('Years of Education')
    ax1.set_ylabel('No. of Countries')
    ax2.hist(dframe['women'])
    ax2.set_title('Women: School Life Expectancy')
    ax2.set_xlabel('Years of Education')
    ax2.set_ylabel('No. of Countries')
    fig.savefig('school_hist.png')
    print ("See 'school_hist.png' for histograms of school life "
           "expectancy by sex")
    print "The 2 distributions appear roughly normal: use means"
    print ("Avg. School Life Expectancy for Men:\t{:.4}"
           .format(dframe['men'].mean()))
    print ("Avg. School Life Expectancy for Women:\t{:.4}"
           .format(dframe['women'].mean()))


def analyze_gdp():
    """See if there is a correlation between GDP and educational life span"""
    conn = lite.connect('world_ed.db')
    dframe = pd.read_sql_query('select country, total, gdp from ed_life '
                               'where gdp is not null', conn)
    fig, (ax1, ax2) = plt.subplots(2, sharey=True)
    fig.subplots_adjust(hspace=0.6)
    ax1.hist(dframe['total'])
    ax1.set_title('Total School Life Expectancy (Both Sexes)')
    ax1.set_xlabel('Years of Education')
    ax1.set_ylabel('No. of Countries')
    ax2.hist(dframe['gdp'])
    ax2.set_title('GDP of Many Countries')
    ax2.set_xlabel('GDP in units of 10 quadrillion (current US$)')
    ax2.set_ylabel('No. of Countries')
    fig.savefig('gdp_school_hist.png')

    print "\nGDP is obviously right skewed (see 'gdp_school_hist.png')"
    print "Log transforming the variable..."

    dframe['log_gdp'] = np.log(dframe['gdp'])
    fig2, ax3 = plt.subplots()
    ax3.scatter(dframe['log_gdp'], dframe['total'])
    ax3.set_title('Scatterplot of log(GDP) vs Educ. Life Expectancy')
    ax3.set_xlabel('log(GDP)')
    ax3.set_ylabel('Educ. Life Expectancy')
    fig2.savefig('gdp_scatter.png')
    print ("See scatterplot of log gdp vs. educ. life expectancy "
           "in 'gdp_scatter.png'")
    corr_table = dframe[['log_gdp', 'total']].corr()
    print ("\nCorrelation between log(GDP) and Educ. Life Expectancy: "
           "{:.3}").format(corr_table['log_gdp'][1])
    print "Creating regression model..."
    model = smf.ols(formula='total ~ log_gdp', data=dframe)
    resp = model.fit()
    print "\nSummary of Regression Model:"
    print resp.summary()


def main():
    """Main Function"""
    if not os.path.isfile('world_ed.db'):
        create_db()
        reslt = scrape_data()
        populate_db(reslt)
        add_gdp()
    profile_data()
    analyze_gdp()

if __name__ == '__main__':
    main()
