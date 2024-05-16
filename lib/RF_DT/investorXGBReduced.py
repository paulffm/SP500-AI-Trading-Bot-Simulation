import pandas as pd
import xgboost as xgb
from classes.investorClass import Investor
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from TAIndicators.atr import averageTrueRange
from TAIndicators.stochasticRsi import stochasticRSI
from TAIndicators.ma import movingAverageConvergenceDivergence
from TAIndicators.adx import averageDirectionalMovementIndex
from TAIndicators.rsi import relativeStrengthIndex
from TAIndicators.bb import bollingerBands
from TAIndicators.aroon import aroon
from classes.investorParamsClass import ATRInvestorParams, ADXInvestorParams, StochasticRSIInvestorParams, MACDInvestorParams, RSIInvestorParams, BBInvestorParams, AroonInvestorParams
import numpy as np
from sklearn.preprocessing import StandardScaler


class InvestorXGBReduced(Investor):
	def __init__(self, initialInvestment, window):
		super().__init__(initialInvestment)
		self.window = window
	def returnBrokerUpdate(self, moneyInvestedToday, data) -> pd.DataFrame:
		return pd.DataFrame(
			{'moneyToInvestXGB': moneyInvestedToday,
			 'investedMoneyXGB': self.investedMoney, 'nonInvestedMoneyXGB': self.nonInvestedMoney},
			index=[0])

	def possiblyInvestMorning(self, data):
		model = self.createAndTrainModel(data['df'])
		res = self.calculateInputsMorning(data['df'])
		self.perToInvest = model.predict([res[-1]])[0]

	def possiblyInvestAfternoon(self, data):
		self.perToInvest = 0

	def plotEvolution(self, expData, stockMarketData, recordPredictedValue=None):
		"""
				Function that plots the actual status of the investor investment as well as the decisions that have been made
				:param indicatorData: Data belonging to the indicator used to take decisions
				:param stockMarketData: df with the stock market data
				:param recordPredictedValue: Predicted data dataframe
				"""
		# Plot indicating the evolution of the total value and contain (moneyInvested and moneyNotInvested)
		fig = go.Figure()
		fig.add_trace(
			go.Scatter(name="Money Invested", x=self.record.index, y=self.record["moneyInvested"], stackgroup="one"))
		fig.add_trace(go.Scatter(name="Money Not Invested", x=self.record.index, y=self.record["moneyNotInvested"],
								 stackgroup="one"))
		fig.add_trace(go.Scatter(name="Total Value", x=self.record.index, y=self.record["totalValue"]))
		fig.update_layout(
			title="Evolution of Porfolio using XGB Reduced (" + self.record.index[0].strftime(
				"%d/%m/%Y") + "-" +
				  self.record.index[-1].strftime("%d/%m/%Y") + ")", xaxis_title="Date",
			yaxis_title="Value [$]", hovermode='x unified')
		fig.write_image("images/EvolutionPorfolioXGBWindow(" + self.record.index[0].strftime(
			"%d_%m_%Y") + "-" +
						self.record.index[-1].strftime("%d_%m_%Y") + ").png", scale=6, width=1080, height=1080)
		# fig.show()

		# Plot indicating the value of the indicator, the value of the stock market and the decisions made
		fig = make_subplots(rows=2, cols=1, specs=[[{"secondary_y": True}],
												   [{"secondary_y": False}]])

		fig.add_trace(go.Scatter(name="Stock Market Value Open", x=self.record.index,
								 y=stockMarketData.Open[-len(self.record.index):]), row=1, col=1, secondary_y=False)
		fig.add_trace(go.Scatter(name="Stock Market Value Close", x=self.record.index,
								 y=stockMarketData.Close[-len(self.record.index):]), row=1, col=1, secondary_y=False)
		fig.add_trace(go.Bar(name="Money Invested Today", x=self.record.index, y=self.record["moneyInvestedToday"]),
					  row=2, col=1, secondary_y=False)

		fig.update_xaxes(title_text="Date", row=1, col=1)
		fig.update_xaxes(title_text="Date", row=2, col=1)
		fig.update_layout(
			title="Decision making under XGB Reduced (" + self.record.index[0].strftime("%d/%m/%Y") + "-" +
				  self.record.index[-1].strftime("%d/%m/%Y") + ")", hovermode='x unified')
		fig.write_image("images/DecisionMakingXGBWindow(" + self.record.index[0].strftime("%d_%m_%Y") + "-" +
						self.record.index[-1].strftime("%d_%m_%Y") + ").png", scale=6, width=1080, height=1080)
		# fig.show()

	def createAndTrainModel(self, df: pd.DataFrame):
		data = df.copy()
		data['Open'] = data['Open'].shift(-1)
		data = data[:-2]  # last is nan and second last is the input for prediction

		res = pd.DataFrame()
		# Intraday return (target)
		res['Target'] = data['Open'] - data['Open'].shift()
		y_target = np.asarray([1 if res.Target[i] > 0 else 0 for i in range(len(res))]).reshape(-1, 1)

		# Return_interday
		res['Return_interday'] = np.log(data['Open']) - np.log(data['Close'])

		# bb_pband_w3_stdDev1.774447792366109
		params = BBInvestorParams(3, 1.775)
		res['bb_pband_w3_stdDev1.774447792366109'] = bollingerBands(data['Close'], params)['pband']

		# Return_open
		res['Return_open'] = np.log(data['Open']) - np.log(data['Open'].shift())

		# adx_pos_w6
		params = ADXInvestorParams(6)
		res['adx_pos_w6'] = averageDirectionalMovementIndex(data['High'], data['Low'], data['Close'], params)['adx_pos']

		# adx_pos_w42
		params = ADXInvestorParams(42)
		res['adx_pos_w42'] = averageDirectionalMovementIndex(data['High'], data['Low'], data['Close'], params)[
			'adx_pos']

		# Volume
		res['Volume'] = data['Volume']

		# adx_neg_w1
		params = ADXInvestorParams(1)
		res['adx_neg_w1'] = averageDirectionalMovementIndex(data['High'], data['Low'], data['Close'], params)['adx_neg']

		# Return_intraday
		res['Return_intraday'] = np.log(data['Close']) - np.log(data['Open'])

		# stochRsi_k_w47_s143_s212
		params = StochasticRSIInvestorParams(47, 43, 12)
		res['stochRsi_k_w47_s143_s212'] = stochasticRSI(data['Close'], params)['k']

		res.dropna(inplace=True)
		y_target = y_target[1:]
		X = res.drop(['Target'], axis=1)

		# include t-window data points as additional features
		inp = X.columns.values.tolist()
		# window mabye 0 to 1,2,3
		X = data_shift(X, self.window, inp)
		X = np.asarray(X)

		model = xgb.XGBClassifier(colsample_bylevel=0.6452280156999572, colsample_bytree=0.9581223733932949, learning_rate=0.06266659029259186,
							  max_depth=14, n_estimators=1000, subsample=1)
		model.fit(X, y_target)

		return model

	def calculateInputsMorning(self, df: pd.DataFrame):
		data = df.copy()
		data['Open'] = data['Open'].shift(-1)
		data = data[:-1]
		res = pd.DataFrame()

		# Return_interday
		res['Return_interday'] = np.log(data['Open']) - np.log(data['Close'])

		# bb_pband_w3_stdDev1.774447792366109
		params = BBInvestorParams(3, 1.775)
		res['bb_pband_w3_stdDev1.774447792366109'] = bollingerBands(data['Close'], params)['pband']

		# Return_open
		res['Return_open'] = np.log(data['Open']) - np.log(data['Open'].shift())

		# adx_pos_w6
		params = ADXInvestorParams(6)
		res['adx_pos_w6'] = averageDirectionalMovementIndex(data['High'], data['Low'], data['Close'], params)['adx_pos']

		# adx_pos_w42
		params = ADXInvestorParams(42)
		res['adx_pos_w42'] = averageDirectionalMovementIndex(data['High'], data['Low'], data['Close'], params)['adx_pos']

		# Volume
		res['Volume'] = data['Volume']

		# adx_neg_w1
		params = ADXInvestorParams(1)
		res['adx_neg_w1'] = averageDirectionalMovementIndex(data['High'], data['Low'], data['Close'], params)['adx_neg']

		# Return_intraday
		res['Return_intraday'] = np.log(data['Close']) - np.log(data['Open'])

		# stochRsi_k_w47_s143_s212
		params = StochasticRSIInvestorParams(47, 43, 12)
		res['stochRsi_k_w47_s143_s212'] = stochasticRSI(data['Close'], params)['k']

		# include t-window data points as additional features
		inp = res.columns.values.tolist()
		# window mabye 0 to 1,2,3
		X = data_shift(res, self.window, inp)
		# print(X)
		X = np.asarray(X)

		return X

def data_shift(X, window, inp):
	X_plc = X
	for i in range(window):
		X_shift_bw = X.shift(periods=(i + 1), fill_value=0)
		inp_bw = [x + f'_-{i + 1}' for x in inp]
		X_shift_bw.columns = inp_bw
		X_plc = pd.concat([X_plc, X_shift_bw], axis=1)

	return X_plc